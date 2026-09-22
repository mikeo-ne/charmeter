# Phase 1 — Are.na Channel Architecture

The goal is a **visual qualitative database**: images carry the aesthetic evidence, text
blocks carry the analysis. Nothing is stored twice; the repo holds structured data, Are.na
holds the visual artefacts and the links back to them.

## 1. Parent hub

**Channel:** `Chartmeter // East Africa Intelligence Hub`
**Status:** Private (flip to Closed once the peer set stabilises)
**Description block (pin as first block):**

> Visual qualitative research + market mapping for East African independent music careers.
> Sub-channels: Baseline, Competitor Matrix, SWOT, Media/DJ/Radio Radar, Swipe Files.
> Audit cadence: monthly. Owner: <name>. Last full audit: <YYYY-MM-DD>.

All sub-channels are **connected** into the hub rather than nested by name only, so the hub
remains the single navigable entry point.

## 2. Naming convention

```
CM / <Layer> / <Qualifier>
```

Examples:

- `CM / Baseline / <Artist Name>`
- `CM / Competitors / Luganda Pop`
- `CM / Competitors / Regional Afrobeats`
- `CM / Competitors / EA Amapiano`
- `CM / Competitors / Dancehall-Reggae`
- `CM / SWOT / <Competitor Name>`
- `CM / Radar / Kampala`
- `CM / Radar / Nairobi`
- `CM / Radar / Dar es Salaam`
- `CM / Swipe / TikTok Hooks`
- `CM / Swipe / IG Rollouts`
- `CM / Swipe / WhatsApp Broadcasts`

The `CM /` prefix keeps the whole system sortable in an Are.na profile that may also hold
unrelated channels.

## 3. Artist Baseline & Identity

Sub-channel: `CM / Baseline / <Artist Name>`

Block inventory (target minimum):

| Block | Type | Notes |
|---|---|---|
| Logo / wordmark | image | Transparent PNG + on-dark variant |
| Press photos | image ×6 | Two crops each: 4:5 and 1:1 |
| Cover art archive | image | Every release, chronological |
| EPK | link/PDF | One canonical, dated URL |
| Social links | text | Handle, follower count, date sampled |
| Milestone log | text | Append-only, one line per event |
| Sonic identity | text | Exact subgenre tags used for benchmarking |

Mirror the structured version in [`../data/artist-baseline.yml`](../data/artist-baseline.yml);
use [`../templates/artist-baseline.md`](../templates/artist-baseline.md) for the Are.na text block.

## 4. Regional Competitor Matrix

One channel **per subgenre**, not per country. Country is a field on the competitor, not a
container — cross-border comparison is the point.

Each competitor contributes to its subgenre channel:

- 3–6 image blocks: latest cover art, a thumbnail from their best-performing short-form
  video, a live/press shot, one merch or visual-identity artefact.
- 1 text block: the SWOT, using [`../templates/competitor-swot.md`](../templates/competitor-swot.md).
- 1 link block: their strongest single piece of content in the last 90 days.

## 5. Strengths & Weaknesses (SWOT) blocks

SWOT text blocks are written **inside** the competitor's subgenre channel and additionally
connected to `CM / SWOT / <Competitor Name>` when a rival warrants deep tracking.

Every SWOT must document:

- **Visual hooks** — recurring framing, colour, typography, thumbnail grammar.
- **Content performance loops** — the repeatable format that reliably outperforms.
- **Engagement drop-offs** — where the funnel leaks (e.g. strong TikTok, dead Boomplay).

Analysis is dated. An undated SWOT is treated as expired.

## 6. Media, DJ & Radio Radar

Channels: `CM / Radar / Kampala`, `/ Nairobi`, `/ Dar es Salaam`.

Track four contact classes, mirrored in [`../data/radar.yml`](../data/radar.yml):

1. **FM stations** — station, show, presenter, submission route, submission window.
2. **Club & mobile DJs** — venue/crew, night, genre lean, preferred file format.
3. **Tastemaker hubs** — blogs, YouTube channels, IG/TikTok curators.
4. **Promo networks** — e.g. HYPush and comparable pooled-distribution services.

Each entry carries a `last_contact` date and an `outcome` so the radar doubles as a CRM.

## 7. Promotion & Marketing Swipe Files

Save **real examples**, not descriptions. Screenshot or embed, then annotate in a text block
using [`../templates/swipe-file-entry.md`](../templates/swipe-file-entry.md):

- the hook in the first 1.5 seconds,
- the format (duet, lyric-reveal, dance loop, behind-the-desk, street-vox),
- observed metrics and date sampled,
- the transferable principle, stated in one sentence.

A swipe file entry without a transferable principle is decoration; delete it.

## 8. Hygiene rules

- **Date everything.** Metrics decay in weeks in this market.
- **One claim per text block.** Keeps blocks re-connectable across channels.
- **No untiered competitors.** See [Phase 2](02-tiered-filtering.md).
- **Prune quarterly.** Blocks older than two quarters move to `CM / Archive`.
