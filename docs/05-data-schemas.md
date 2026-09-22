# Data Schemas

All files in `data/` use a deliberately restricted YAML subset: mappings, lists of mappings,
scalars and one level of nesting. This keeps `scripts/chartmeter.py` dependency-free.

Formatting rules:
- Two-space indentation, no tabs.
- Dates are `YYYY-MM-DD`.
- Shares/rates are decimals (`0.18` = 18%).
- Strings containing `:` must be quoted.

---

## `artist-baseline.yml`

| Field | Type | Notes |
|---|---|---|
| `name` | string | Target artist |
| `country` | enum | `UG` `KE` `TZ` `RW` … |
| `city` | string | Home market |
| `subgenre` | tag | Primary benchmarking tag (see Phase 2) |
| `secondary_subgenres` | tag | Informational only |
| `tier` | enum | `upcoming` \| `mid` \| `aspirational` |
| `arena_channel` | string | `CM / Baseline / <Name>` |
| `epk_url` | url | Canonical, dated |
| `last_audit` | date | Stale >45 days triggers a validator warning |
| `metrics` | map | See metric block below |
| `socials` | map | Platform → follower count |
| `milestones` | list | `YYYY-MM-DD \| description`, append-only |

### Metric block (shared by baseline and competitors)

| Metric | Type | Definition |
|---|---|---|
| `monthly_listeners` | int | Spotify monthly listeners (or best available equivalent) |
| `boomplay_streams` | int | Lifetime streams |
| `shortform_posts_per_week` | int | Trailing 4-week average |
| `shortform_median_views` | int | Median, never mean — one viral post distorts the mean |
| `dj_spins_30d` | int | Distinct DJs confirmed, last 30 days |
| `radio_adds_30d` | int | Station rotations added, last 30 days |
| `editorial_playlist_adds_90d` | int | Human-curated only; algorithmic excluded |
| `whatsapp_list_size` | int | Broadcast list contacts |
| `live_shows_90d` | int | Paid or promotional performances |
| `crossborder_listener_share` | float | Share of listeners outside home country |

---

## `competitors.yml`

Root key `competitors`, a list. Fields: all metric-block fields under `metrics`, plus:

| Field | Type | Notes |
|---|---|---|
| `name` `country` `city` | string | |
| `subgenre` | tag | Must match the target artist's tag to be compared |
| `tier` | enum | Validator cross-checks against `monthly_listeners` |
| `active_last_120d` | bool | Phase 2 admission requirement |
| `last_audit` | date | |
| `arena_channel` | string | |
| `visual_hooks` | string | SWOT: recurring visual grammar |
| `performance_loop` | string | SWOT: the repeatable outperforming format |
| `dropoff` | string | SWOT: where the funnel leaks |

Tier boundaries: `upcoming` 0–20,000 · `mid` 20,000–500,000 · `aspirational` >500,000.

---

## `radar.yml`

Root key `contacts`, a list.

| Field | Type | Notes |
|---|---|---|
| `name` | string | Station, DJ, crew, hub or network |
| `class` | enum | `fm` \| `dj` \| `tastemaker` \| `promo-network` |
| `city` | string | Kampala / Nairobi / Dar es Salaam / … |
| `handle` | string | Email, phone or @handle — quote if it contains `:` |
| `genre_lean` | tag | Or `multi` |
| `submission_route` | string | Exact mechanism and window |
| `last_contact` | date | |
| `outcome` | string | Required; `Pending review` is a valid outcome |

---

## `swipe-file.yml`

Root key `entries`, a list.

| Field | Type | Notes |
|---|---|---|
| `source` | string | Who ran it |
| `channel` | enum | `tiktok` \| `instagram` \| `whatsapp` \| `youtube` \| `radio` |
| `date` | date | When sampled |
| `hook` | string | What happens in the first 1.5 seconds |
| `format` | string | The mechanic |
| `metrics` | string | Observed numbers, as sampled |
| `principle` | string | **Required.** One transferable sentence. |
