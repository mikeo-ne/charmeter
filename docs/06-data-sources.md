# Automated Data Sources

Stop typing stats in by hand. `scripts/fetch_stats.py` pulls what is genuinely
available from platform APIs and writes it straight into `data/`.

**The honest headline:** roughly half of the Chartmeter metric set is fetchable.
The other half is deliberately manual, because no API exposes it. This page says
exactly which is which so you never wonder whether a number is stale or invented.

---

## What each provider gives you

| Provider | Auth | Cost | Fills | Verdict for East Africa |
|---|---|---|---|---|
| **Boomplay OpenAPI** | `app_id` + `app_secret` (partner) | Free, approval needed | `boomplay_streams` | **The most important one.** Official `total_streams` per artist, plus per-country play analytics on albums. Boomplay is where this market's demand shows first. |
| **YouTube Data API v3** | API key | Free, 10k units/day | `youtube_subscribers`, `youtube_views` | Easiest win. `channels.list` costs 1 unit, so a 20-act refresh uses 20 of 10,000. |
| **Last.fm** | API key | Free, instant | `lastfm_listeners`, `lastfm_playcount` | Instant key, no approval. Sample skews non-African — use as a **trend line**, not an absolute. |
| **MusicBrainz** | none | Free | `release_count` | Keyless. Identity and discography only, no performance data. Rate-limited to 1 req/sec. |
| **Spotify Web API** | client id + secret | Free | `spotify_followers`, `spotify_popularity` | **Does NOT provide monthly listeners.** See below. |

Check your setup any time:

```bash
python3 scripts/fetch_stats.py --check
```

---

## The Spotify problem (read this before asking why)

**There is no official API endpoint for Spotify monthly listeners.** Spotify staff
confirmed this directly on the developer community, and it has only got worse:

- **Nov 2024** — catalogue endpoints restricted for development-mode apps.
- **May 15 2025** — extended quota applications accepted from *organisations only*,
  requiring a registered business, a launched service, and **250,000+ monthly active users**.
- **Feb 11 / Mar 9 2026** — a further migration removed more endpoint families and
  cut the search cap to 10.

For an independent Ugandan act, extended quota is unreachable by definition. So
Chartmeter treats `monthly_listeners` as a **manual field** and refuses to write it
automatically. The script hard-blocks it: even if a provider returned the key, the
runner drops it.

Third-party scrapers (Apify, RapidAPI) do sell monthly-listener numbers. Chartmeter
does not use them — they violate Spotify's Developer Terms, break without warning,
and cost money. **Use Spotify for Artists**, which shows you your own numbers for
free and is the authoritative source. For competitors, read the public figure off
their artist page once a month.

What Spotify *does* give you officially is `followers` and `popularity` (0–100).
Chartmeter stores these under their own keys so they are never silently mistaken for
monthly listeners.

---

## Manual-only metrics, and why

| Metric | Where it actually comes from |
|---|---|
| `monthly_listeners` | Spotify for Artists (yours) / public artist page (rivals) |
| `shortform_posts_per_week` | The account itself — TikTok/IG research APIs are gated to academics |
| `shortform_median_views` | The account or your creator dashboard |
| `dj_spins_30d` | **Fieldwork.** Ask the DJs. This is the point of the radar. |
| `radio_adds_30d` | Station contacts |
| `editorial_playlist_adds_90d` | Spotify / Apple for Artists |
| `whatsapp_list_size` | Your own broadcast list |
| `live_shows_90d` | Your own calendar |
| `crossborder_listener_share` | Spotify / Boomplay for Artists audience tab |

This is not a limitation to route around — `dj_spins_30d` and `whatsapp_list_size`
are your **highest-signal metrics in this market**, and they are exactly the ones no
platform will ever hand you. The automation exists to clear away the boring numbers
so you spend your time on the fieldwork that actually differentiates the analysis.

---

## Setup

### 1. Get keys

- **YouTube** — Google Cloud Console → new project → enable *YouTube Data API v3* → create an API key. Minutes.
- **Last.fm** — <https://www.last.fm/api/account/create>. Instant.
- **Spotify** — <https://developer.spotify.com/dashboard> → create app → client id + secret. Minutes.
- **Boomplay** — <https://developer.boomplay.com/> → apply for partner access. This one takes human approval; it is worth chasing, as it is the most relevant dataset for your market.
- **MusicBrainz** — nothing needed.

### 2. Store them

```bash
cp .env.example .env
$EDITOR .env          # .env is gitignored - never commit it
```

### 3. Map artists to platform ids

Edit `data/sources.yml`. Names must match `artist-baseline.yml` and `competitors.yml`
exactly. Blank id = that provider is skipped for that act.

```yaml
artists:
  - name: Nsimbi
    boomplay: "40002868"          # from boomplay.com/artists/<ID>
    youtube: "UCxxxxxxxxxxxxxxxxxxxxxx"   # or "@handle"
    lastfm: "Nsimbi"
    spotify: "3TVXtAsR1Inumwj472S9r4"
```

### 4. Run

```bash
python3 scripts/fetch_stats.py --check      # what is configured
python3 scripts/fetch_stats.py --dry-run    # preview, writes nothing
python3 scripts/fetch_stats.py              # write into data/
python3 scripts/fetch_stats.py --history    # also append to data/history.csv
python3 scripts/chartmeter.py gaps          # re-run the analysis
```

Useful flags: `--only boomplay,youtube` to limit providers, `--artist "Nsimbi"` to
limit to one act.

---

## How writes work

The script edits YAML **line by line** rather than re-serialising, so your comments,
ordering and hand-written SWOT notes survive untouched. It:

- only ever writes keys inside an artist's `metrics:` block;
- never writes a manual-only metric, even if a provider returns one;
- stamps `_fetched: <date>` on each updated block;
- leaves everything alone on failure — one dead provider never blocks the rest.

**Always `--dry-run` first**, and commit before a big run so the diff is reviewable.

## Trend history

`--history` appends every reading to `data/history.csv` (`date,artist,provider,metric,value`).
That gives you month-over-month deltas — the thing a single snapshot can never show,
and the reason to run this on a schedule rather than ad hoc.

## Scheduled refresh

`.github/workflows/refresh-stats.yml` runs monthly (and on demand), fetches with
whatever repository secrets you have set, and opens a pull request with the diff. Add
your keys under **Settings → Secrets and variables → Actions**. No secrets set = the
job no-ops harmlessly.

Locally, monthly via cron:

```cron
0 9 1 * * cd /path/to/charmeter && python3 scripts/fetch_stats.py --history
```

## Rate limits and etiquette

- Retries with exponential backoff on 429/5xx, honouring `Retry-After`.
- MusicBrainz is throttled to 1 request/second per their policy.
- Every request sends a descriptive User-Agent.
- YouTube: a 20-act refresh costs ~20 of 10,000 daily units.
