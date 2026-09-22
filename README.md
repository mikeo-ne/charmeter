# Chartmeter // East Africa Intelligence Hub

A visual-qualitative research and market-mapping system for East African independent music
careers, built on top of [Are.na](https://are.na) channels plus a lightweight local
repository of templates, schemas and tooling.

Chartmeter answers three questions continuously:

1. **Where does the artist actually stand?** (Baseline & Identity)
2. **Who is the *true* peer set, tier-matched and subgenre-matched?** (Competitor Matrices)
3. **What is the next highest-leverage regional move?** (Promotion & Distribution Playbook)

---

## Master System Architecture

| Layer | Purpose | Lives in |
|---|---|---|
| Parent Hub Channel | `Chartmeter // East Africa Intelligence Hub` — container for all sub-channels | Are.na |
| Artist Baseline & Identity | Branding, press photos, EPK, social links, milestone log | Are.na + `data/artist-baseline.yml` |
| Competitor & SWOT Matrices | Image blocks of rival hooks + text blocks of analysis | Are.na + `data/competitors.yml` |
| Media, DJ & Radio Radar | FM stations, club DJs, tastemaker hubs, promo networks | `data/radar.yml` |
| Swipe Files | Winning TikTok hooks, IG rollouts, WhatsApp campaigns | Are.na + `data/swipe-file.yml` |
| Execution & Growth Workflow | Audit cadence, gap analysis, campaign pivots | `docs/04-execution-workflow.md` |

## Documentation

- [`docs/01-arena-architecture.md`](docs/01-arena-architecture.md) — Phase 1: channel architecture & naming conventions
- [`docs/02-tiered-filtering.md`](docs/02-tiered-filtering.md) — Phase 2: filtering true competition by career tier
- [`docs/03-regional-playbook.md`](docs/03-regional-playbook.md) — Phase 3: regional promotion & distribution tactics
- [`docs/04-execution-workflow.md`](docs/04-execution-workflow.md) — auditing cadence & strategic gap analysis
- [`docs/05-data-schemas.md`](docs/05-data-schemas.md) — field reference for everything in `data/`
- [`docs/06-data-sources.md`](docs/06-data-sources.md) — **automated stat fetching**: which APIs work, which don't, and why
- [`docs/07-demo-guide.md`](docs/07-demo-guide.md) — **running a client demo**: the ten-minute script

## Templates

Copy-paste scaffolds for Are.na text blocks: [`templates/`](templates/)

- `competitor-swot.md` — per-competitor SWOT block
- `artist-baseline.md` — baseline/identity block
- `dj-seeding-tracker.md` — DJ & club seeding workflow
- `swipe-file-entry.md` — swipe file capture format
- `campaign-brief.md` — release/campaign one-pager

## Tooling

```bash
python3 scripts/chartmeter.py validate   # sanity-check the data files
python3 scripts/chartmeter.py tiers      # group competitors by tier
python3 scripts/chartmeter.py gaps       # artist vs. competitor gap analysis
python3 scripts/chartmeter.py report     # full markdown report -> stdout
```

No third-party dependencies beyond Python 3.8+ (`scripts/chartmeter.py` ships a minimal
YAML subset parser so it runs anywhere).

## The web app

An interactive client-facing app — dashboard, gap analysis, and an editable
competitor matrix that enforces the tiering rules:

```bash
python3 scripts/server.py --port 3000    # then open http://localhost:3000
```

Stdlib only, no build step. Analysis is imported from `chartmeter.py`, so the web app
and the CLI can never disagree. Demo edits go to a gitignored working copy
(`data/workspace.json`) — `data/*.yml` is never modified, and **Reset demo data**
restores the seed. Demo script in [`docs/07-demo-guide.md`](docs/07-demo-guide.md).

## Automated stat fetching

Stop entering numbers by hand. `scripts/fetch_stats.py` pulls from platform APIs
straight into `data/`:

```bash
cp .env.example .env                        # add your keys (gitignored)
python3 scripts/fetch_stats.py --check      # which providers are configured
python3 scripts/fetch_stats.py --dry-run    # preview, writes nothing
python3 scripts/fetch_stats.py --history    # write + log to data/history.csv
```

| Provider | Fills | Notes |
|---|---|---|
| Boomplay OpenAPI | `boomplay_streams` | Most relevant for East Africa; partner approval needed |
| YouTube Data API v3 | `youtube_subscribers`, `youtube_views` | Free key, 10k units/day |
| Last.fm | `lastfm_listeners`, `lastfm_playcount` | Instant free key; trend line only |
| MusicBrainz | `release_count` | Keyless |
| Spotify | `spotify_followers`, `spotify_popularity` | **No monthly listeners — no API exposes them** |

Fieldwork metrics (DJ spins, radio adds, WhatsApp list, live shows) and
`monthly_listeners` stay manual by design; the script refuses to write them.
Full detail and setup in [`docs/06-data-sources.md`](docs/06-data-sources.md).
A monthly GitHub Action (`.github/workflows/refresh-stats.yml`) can do the refresh
and open a PR with the diff.

## Site & deployment

The whole hub renders to a static site — docs, templates, and a live report generated
from `data/` at build time:

```bash
python3 scripts/build_site.py            # -> site/
python3 -m http.server 3000 --directory site
```

The build is also dependency-free (`build_site.py` renders the Markdown subset this repo
uses), so CI needs no install step. Pushes to `main` build and publish to GitHub Pages via
[`.github/workflows/deploy.yml`](.github/workflows/deploy.yml); enable it once under
**Settings → Pages → Source: GitHub Actions**. `site/` is gitignored — it is a build artifact.

## Quick start

1. Create the Are.na parent hub channel and sub-channels per `docs/01-arena-architecture.md`.
2. Fill in `data/artist-baseline.yml` with your target artist.
3. Add 8–15 tier-matched, subgenre-matched rivals to `data/competitors.yml`.
4. Populate `data/radar.yml` with Kampala / Nairobi / Dar es Salaam contacts.
5. Run `python3 scripts/chartmeter.py report > report.md` and work the gaps.
6. Re-audit monthly; log deltas in the milestone list.
