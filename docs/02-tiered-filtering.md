# Phase 2 — Filtering True Competition by Career Tier

Benchmarking an artist at 6k monthly listeners against a continental headliner produces
demoralising, non-actionable data. Chartmeter enforces **two filters before any competitor
enters the matrix**.

## Filter A — Career tier

| Tier | Monthly listeners | Primary focus | Benchmark question |
|---|---|---|---|
| **Upcoming** | 0 – 20,000 | Grassroots metrics, local DJ rotation in clubs and hangouts, micro-content loops on TikTok & Instagram | Who is driving initial campus and neighbourhood buzz right now? |
| **Mid-Level** | 20,000 – 500,000 | Platform analytics across Boomplay, Apple Music, Spotify; regional playlist placement | Who is securing steady editorial slots and cross-border streaming traction? |

Anything above 500k is logged as **Aspirational** — studied for tactics, never used as a
performance benchmark.

### Upcoming tier — what to actually measure

- Club/hangout rotation: number of distinct DJs confirmed playing the track in 30 days.
- Campus footprint: named universities/halls where the track has been performed or played.
- Micro-content loop health: posts/week, median views, save rate, sound re-uses by others.
- WhatsApp/status shares — ask DJs and fans directly; this is the region's real virality signal.
- Boomplay early-window plays (Boomplay indexes grassroots demand earlier than Spotify here).

### Mid-Level tier — what to actually measure

- Boomplay: streams, chart position by country, favourites-to-stream ratio.
- Apple Music / Spotify: monthly listeners, top 5 cities, playlist adds (editorial vs algorithmic).
- Cross-border split: % of listeners in UG / KE / TZ / RW / diaspora.
- Editorial cadence: number of editorial slots in last 6 months and which curators repeat.
- Release-to-playlist latency: days from release to first editorial add.

## Filter B — Sonic alignment

A competitor must share the **exact subgenre**, not merely the region. Supported tags:

- `luganda-pop`
- `regional-afrobeats`
- `ea-amapiano`
- `dancehall-reggae`
- `kidandali`
- `gengetone`
- `bongo-flava`
- `afro-house`

Rules:

1. A competitor enters the matrix on **one primary tag**; secondary tags are informational.
2. Cross-tag comparison is allowed only in the Swipe Files, never in performance tables.
3. If the target artist straddles two tags, run **two parallel matrices** rather than one blended one.

## The admission checklist

Before adding a competitor, all five must be true:

- [ ] Same primary subgenre tag as the target artist.
- [ ] Same career tier (Upcoming or Mid-Level).
- [ ] Active in the last 120 days (release, tour date, or sustained content).
- [ ] Operating in or actively targeting UG / KE / TZ.
- [ ] At least one metric is independently verifiable and dated.

Failing any line → the act goes to `CM / Archive / Not Peers` with a one-line reason.

## Sample size

- Upcoming tier: 8–12 peers. Fewer, and the noise floor dominates.
- Mid-Level tier: 6–10 peers plus 3 aspirational acts for tactic-mining only.

Re-tier every quarter. Artists cross the 20k line fast; a stale tier silently corrupts the
whole gap analysis.

## Where this is encoded

`data/competitors.yml` carries `tier` and `subgenre` on every entry.
`python3 scripts/chartmeter.py tiers` prints the grouped view and flags any competitor whose
`tier` disagrees with its `monthly_listeners`, or whose subgenre does not match the target artist.
