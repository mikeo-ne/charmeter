#!/usr/bin/env python3
"""Parse pasted platform URLs into provider ids, and sync stats from them.

The user pastes any of these and Chartmeter works out the rest:

    https://open.spotify.com/artist/3TVXtAsR1Inumwj472S9r4
    https://www.boomplay.com/artists/40002868
    https://youtube.com/@somehandle          or /channel/UC...
    https://www.last.fm/music/Eddy+Kenzo
    https://audiomack.com/some-artist
    https://musicbrainz.org/artist/<uuid>

Anything unrecognised is reported back clearly rather than silently ignored.
"""

from __future__ import annotations

import os
import re
import sys
from urllib.parse import unquote, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import providers  # noqa: E402

# host fragment -> (provider key, path regex, label)
PATTERNS = [
    ("spotify", r"open\.spotify\.com", r"/artist/([A-Za-z0-9]+)", "Spotify"),
    ("boomplay", r"boomplay\.com", r"/artists?/(\d+)", "Boomplay"),
    ("youtube", r"(youtube\.com|youtu\.be)", r"/channel/(UC[A-Za-z0-9_-]{22})", "YouTube"),
    ("youtube", r"(youtube\.com|youtu\.be)", r"/(@[A-Za-z0-9._-]+)", "YouTube"),
    ("lastfm", r"last\.fm", r"/music/([^/?#]+)", "Last.fm"),
    ("audiomack", r"audiomack\.com", r"/([A-Za-z0-9._-]+)", "Audiomack"),
    ("musicbrainz", r"musicbrainz\.org", r"/artist/([0-9a-fA-F-]{36})", "MusicBrainz"),
]

LABELS = {
    "spotify": "Spotify",
    "boomplay": "Boomplay",
    "youtube": "YouTube",
    "lastfm": "Last.fm",
    "audiomack": "Audiomack",
    "musicbrainz": "MusicBrainz",
}

# Which platforms can currently be auto-synced, and what they yield.
SYNCABLE = {
    "boomplay": ["boomplay_streams"],
    "youtube": ["youtube_subscribers", "youtube_views"],
    "lastfm": ["lastfm_listeners", "lastfm_playcount"],
    "musicbrainz": ["release_count"],
    "spotify": ["spotify_followers", "spotify_popularity"],
}


def parse_link(url: str):
    """-> (provider_key, identifier, label) or (None, None, None)."""
    url = (url or "").strip()
    if not url:
        return None, None, None
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    try:
        parsed = urlparse(url)
    except ValueError:
        return None, None, None

    host = (parsed.netloc or "").lower()
    path = parsed.path or "/"

    for key, host_re, path_re, label in PATTERNS:
        if not re.search(host_re, host):
            continue
        m = re.search(path_re, path)
        if m:
            ident = unquote(m.group(1))
            if key == "lastfm":
                ident = ident.replace("+", " ")
            if key == "audiomack" and ident in ("artist", "song", "album", "playlist"):
                continue
            return key, ident, label
    return None, None, None


def parse_many(urls) -> dict:
    """Parse a list/blob of URLs -> {'links': {key: {...}}, 'unknown': [...]}"""
    if isinstance(urls, str):
        urls = re.split(r"[\s,]+", urls)
    links, unknown = {}, []
    for raw in urls:
        raw = (raw or "").strip()
        if not raw:
            continue
        key, ident, label = parse_link(raw)
        if key:
            links[key] = {"id": ident, "url": raw, "label": label,
                          "syncable": key in SYNCABLE}
        else:
            unknown.append(raw)
    return {"links": links, "unknown": unknown}


def sync(links: dict) -> dict:
    """Fetch stats for parsed links.

    Returns {'metrics': {...}, 'results': [per-platform status], 'needs_setup': [...]}.
    Never raises - every platform reports its own outcome so partial success works.
    """
    metrics, results, needs_setup = {}, [], []

    for key, info in (links or {}).items():
        label = LABELS.get(key, key)
        if key not in SYNCABLE:
            results.append({"platform": key, "label": label, "status": "unsupported",
                            "detail": "No API available for this platform."})
            continue
        try:
            provider = providers.get(key)
        except KeyError:
            results.append({"platform": key, "label": label, "status": "unsupported",
                            "detail": "No connector."})
            continue

        if not provider.available():
            needs_setup.append(label)
            results.append({
                "platform": key, "label": label, "status": "needs_key",
                "detail": "Set %s to enable." % ", ".join(provider.missing()),
            })
            continue

        try:
            got = provider.fetch(str(info.get("id")))
        except providers.ProviderError as exc:
            results.append({"platform": key, "label": label, "status": "error",
                            "detail": str(exc)})
            continue
        except Exception as exc:  # noqa: BLE001
            results.append({"platform": key, "label": label, "status": "error",
                            "detail": repr(exc)})
            continue

        clean = {k: v for k, v in got.items()
                 if not k.startswith("_") and k not in providers.MANUAL_ONLY}
        metrics.update(clean)
        results.append({
            "platform": key, "label": label, "status": "ok",
            "detail": ", ".join("%s=%s" % (k, v) for k, v in sorted(clean.items())) or "no data",
            "metrics": clean,
        })

    return {"metrics": metrics, "results": results, "needs_setup": needs_setup}
