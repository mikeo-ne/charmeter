#!/usr/bin/env python3
"""Streaming/platform API connectors for Chartmeter.

Each provider exposes:
    NAME        - short id used in data/sources.yml and on the CLI
    ENV         - env vars required for credentials (empty = keyless)
    METRICS     - Chartmeter metric keys it can populate
    available() - credentials present?
    fetch(id)   - {metric_key: value}; raises ProviderError on failure

Only stdlib is used so the repo stays dependency-free.

IMPORTANT — what is and is not fetchable (see docs/06-data-sources.md):
  * Spotify monthly listeners are NOT exposed by any official API endpoint.
    Spotify staff confirmed this on the developer community, and the Feb/Mar
    2026 lockdown removed further catalogue endpoints from development-mode
    apps. Chartmeter therefore treats monthly_listeners as a manual field and
    refuses to invent it.
  * Boomplay total_streams IS available via the official OpenAPI (partner
    credentials required) and maps cleanly onto boomplay_streams.
  * Everything else (DJ spins, radio adds, WhatsApp list, live shows) is
    off-platform fieldwork and stays manual by design.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "chartmeter/1.0 (+https://github.com/mikeo-ne/charmeter)"
TIMEOUT = 25


class ProviderError(RuntimeError):
    """Recoverable per-provider failure; the runner logs and continues."""


def _request(url, *, headers=None, data=None, method=None, retries=3):
    hdrs = {"User-Agent": UA, "Accept": "application/json"}
    hdrs.update(headers or {})
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        hdrs.setdefault("Content-Type", "application/json")

    last = None
    for attempt in range(retries):
        req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                raw = resp.read().decode("utf-8", "replace")
            return json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:200]
            # Back off on rate limit / server errors, fail fast on 4xx.
            if exc.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                wait = int(exc.headers.get("Retry-After") or 2 ** (attempt + 1))
                time.sleep(min(wait, 30))
                last = ProviderError("HTTP %s: %s" % (exc.code, detail))
                continue
            raise ProviderError("HTTP %s: %s" % (exc.code, detail)) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last = ProviderError("network: %s" % exc)
            if attempt < retries - 1:
                time.sleep(2 ** (attempt + 1))
                continue
            raise last from exc
        except json.JSONDecodeError as exc:
            raise ProviderError("non-JSON response") from exc
    raise last or ProviderError("unreachable")


class Provider:
    NAME = ""
    ENV: tuple = ()
    METRICS: tuple = ()
    NOTE = ""

    def available(self) -> bool:
        return all(os.environ.get(v) for v in self.ENV)

    def missing(self) -> list:
        return [v for v in self.ENV if not os.environ.get(v)]

    def fetch(self, ident: str) -> dict:
        raise NotImplementedError


# --------------------------------------------------------------------------- Boomplay

class Boomplay(Provider):
    """Official Boomplay OpenAPI — the key source for this market.

    Auth: client-credentials POST /oauth/token -> access token.
    Artist endpoint returns total_streams and likes.
    Docs: https://developer.boomplay.com/
    Requires partner credentials from Boomplay (apply via their developer portal).
    """

    NAME = "boomplay"
    ENV = ("BOOMPLAY_APP_ID", "BOOMPLAY_APP_SECRET")
    METRICS = ("boomplay_streams",)
    NOTE = "Official OpenAPI; needs partner app_id/app_secret."
    BASE = "https://openapi.boomplay.com"

    def __init__(self):
        self._token = None

    def _auth(self) -> str:
        if self._token:
            return self._token
        payload = {
            "grant_type": "clientCredentials",
            "app_id": os.environ["BOOMPLAY_APP_ID"],
            "app_secret": os.environ["BOOMPLAY_APP_SECRET"],
        }
        res = _request(self.BASE + "/oauth/token", data=payload, method="POST")
        data = res.get("data") or res
        tok = data.get("access_token") or data.get("accessToken")
        if not tok:
            raise ProviderError("no access_token in token response: %s" % str(res)[:160])
        self._token = tok
        return tok

    def fetch(self, ident: str) -> dict:
        tok = self._auth()
        url = "%s/artist/v1/artistIds?%s" % (self.BASE, urllib.parse.urlencode({"ids": ident}))
        res = _request(url, headers={
            "Authorization": tok if tok.lower().startswith("bearer") else "Bearer " + tok,
            "app_id": os.environ["BOOMPLAY_APP_ID"],
        })
        rows = res.get("data") or []
        if isinstance(rows, dict):
            rows = [rows]
        if not rows:
            raise ProviderError("artist id %s not found" % ident)
        row = rows[0]
        out = {}
        if row.get("total_streams") is not None:
            out["boomplay_streams"] = int(row["total_streams"])
        if row.get("likes") is not None:
            out["_boomplay_likes"] = int(row["likes"])
        return out


# --------------------------------------------------------------------------- YouTube

class YouTube(Provider):
    """YouTube Data API v3 channels.list — 1 quota unit per call, 10k/day free.

    Batches up to 50 channel ids, but Chartmeter calls per-artist for clarity;
    at 1 unit each that is irrelevant against the daily quota.
    Note: subscriber counts are rounded by YouTube for channels over 1k.
    """

    NAME = "youtube"
    ENV = ("YOUTUBE_API_KEY",)
    METRICS = ("youtube_subscribers", "youtube_views")
    NOTE = "Free, 10k quota units/day; channels.list costs 1 unit."
    BASE = "https://www.googleapis.com/youtube/v3"

    def fetch(self, ident: str) -> dict:
        key = os.environ["YOUTUBE_API_KEY"]
        params = {"part": "statistics,snippet", "key": key}
        if ident.startswith("UC") and len(ident) == 24:
            params["id"] = ident
        else:
            params["forHandle"] = ident if ident.startswith("@") else "@" + ident
        res = _request(self.BASE + "/channels?" + urllib.parse.urlencode(params))
        items = res.get("items") or []
        if not items:
            raise ProviderError("channel %s not found" % ident)
        st = items[0].get("statistics", {})
        out = {}
        if st.get("subscriberCount") is not None:
            out["youtube_subscribers"] = int(st["subscriberCount"])
        if st.get("viewCount") is not None:
            out["youtube_views"] = int(st["viewCount"])
        return out


# --------------------------------------------------------------------------- Last.fm

class LastFM(Provider):
    """Last.fm artist.getInfo — free API key, global listener/playcount proxy.

    Not a substitute for Spotify monthly listeners: Last.fm's sample skews
    heavily non-African, so treat it as a trend line, not an absolute.
    """

    NAME = "lastfm"
    ENV = ("LASTFM_API_KEY",)
    METRICS = ("lastfm_listeners", "lastfm_playcount")
    NOTE = "Free key, instant. Sample skews non-African - trend only."
    BASE = "https://ws.audioscrobbler.com/2.0/"

    def fetch(self, ident: str) -> dict:
        params = {
            "method": "artist.getinfo",
            "artist": ident,
            "api_key": os.environ["LASTFM_API_KEY"],
            "format": "json",
            "autocorrect": "1",
        }
        res = _request(self.BASE + "?" + urllib.parse.urlencode(params))
        if res.get("error"):
            raise ProviderError("lastfm %s: %s" % (res.get("error"), res.get("message")))
        stats = ((res.get("artist") or {}).get("stats")) or {}
        out = {}
        if stats.get("listeners") is not None:
            out["lastfm_listeners"] = int(stats["listeners"])
        if stats.get("playcount") is not None:
            out["lastfm_playcount"] = int(stats["playcount"])
        return out


# --------------------------------------------------------------------------- MusicBrainz

class MusicBrainz(Provider):
    """MusicBrainz — keyless, open. Identity/discography, not performance.

    Used to resolve canonical artist identity and release counts so the
    baseline stays accurate. Rate limit: 1 req/sec, enforced below.
    """

    NAME = "musicbrainz"
    ENV = ()
    METRICS = ("release_count",)
    NOTE = "Keyless and open. Identity + release counts, no stream data."
    BASE = "https://musicbrainz.org/ws/2"

    def fetch(self, ident: str) -> dict:
        time.sleep(1.1)  # MusicBrainz asks for <=1 request/second
        url = "%s/release-group?artist=%s&fmt=json&limit=100" % (self.BASE, urllib.parse.quote(ident))
        res = _request(url)
        if "release-group-count" in res:
            return {"release_count": int(res["release-group-count"])}
        return {"release_count": len(res.get("release-groups") or [])}


# --------------------------------------------------------------------------- Spotify

class Spotify(Provider):
    """Spotify Web API — catalogue only.

    Deliberately does NOT attempt monthly listeners: no official endpoint
    exists, and scraping it violates Spotify's Developer Terms. Returns the
    popularity score (0-100) and follower count, which ARE official, and are
    stored under distinct keys so they are never confused with monthly
    listeners in the gap analysis.
    """

    NAME = "spotify"
    ENV = ("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET")
    METRICS = ("spotify_followers", "spotify_popularity")
    NOTE = "Followers + popularity only. Monthly listeners are NOT in any API."
    TOKEN_URL = "https://accounts.spotify.com/api/token"
    BASE = "https://api.spotify.com/v1"

    def __init__(self):
        self._token = None

    def _auth(self) -> str:
        if self._token:
            return self._token
        import base64
        cid = os.environ["SPOTIFY_CLIENT_ID"]
        sec = os.environ["SPOTIFY_CLIENT_SECRET"]
        basic = base64.b64encode(("%s:%s" % (cid, sec)).encode()).decode()
        req = urllib.request.Request(
            self.TOKEN_URL,
            data=urllib.parse.urlencode({"grant_type": "client_credentials"}).encode(),
            headers={
                "Authorization": "Basic " + basic,
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": UA,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                tok = json.loads(resp.read().decode()).get("access_token")
        except urllib.error.HTTPError as exc:
            raise ProviderError("token: HTTP %s" % exc.code) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ProviderError("token: %s" % exc) from exc
        if not tok:
            raise ProviderError("no access_token")
        self._token = tok
        return tok

    def fetch(self, ident: str) -> dict:
        tok = self._auth()
        res = _request("%s/artists/%s" % (self.BASE, ident),
                       headers={"Authorization": "Bearer " + tok})
        out = {}
        if (res.get("followers") or {}).get("total") is not None:
            out["spotify_followers"] = int(res["followers"]["total"])
        if res.get("popularity") is not None:
            out["spotify_popularity"] = int(res["popularity"])
        return out


REGISTRY = {p.NAME: p for p in (Boomplay, YouTube, LastFM, MusicBrainz, Spotify)}

# Metrics no API can supply - these stay manual, by design.
MANUAL_ONLY = {
    "monthly_listeners": "No official API exposes Spotify monthly listeners; enter from Spotify for Artists.",
    "shortform_posts_per_week": "Count from the account; TikTok/IG research APIs are gated.",
    "shortform_median_views": "Count from the account or creator dashboard.",
    "dj_spins_30d": "Fieldwork - confirm with DJs directly.",
    "radio_adds_30d": "Fieldwork - confirm with stations.",
    "editorial_playlist_adds_90d": "Spotify/Apple for Artists dashboards.",
    "whatsapp_list_size": "Your own broadcast list.",
    "live_shows_90d": "Your own calendar.",
    "crossborder_listener_share": "Spotify/Boomplay for Artists audience tab.",
}


def get(name: str) -> Provider:
    if name not in REGISTRY:
        raise KeyError(name)
    return REGISTRY[name]()
