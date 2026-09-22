# Execution & Growth Workflow

## Cadence

| Rhythm | Activity | Output |
|---|---|---|
| Weekly (30 min) | Swipe-file capture: 3 new hooks, 1 IG rollout, 1 WhatsApp campaign | New blocks in `CM / Swipe / *` |
| Bi-weekly (45 min) | Radar refresh: update `last_contact` / `outcome` on DJ & media entries | Updated `data/radar.yml` |
| Monthly (2 h) | Competitor metric pull + SWOT re-dating | Updated `data/competitors.yml`, fresh SWOT blocks |
| Quarterly (half day) | Re-tiering, peer-set pruning, full gap analysis, campaign pivot | `report.md` + next-quarter campaign brief |

## Continuous auditing

Each audit pass asks, per competitor:

1. What did they ship since the last audit?
2. Which single piece outperformed, and what was the hook in the first 1.5 seconds?
3. What did they repeat? (Repetition = the loop they believe in.)
4. Where did they leak? (Strong platform vs dead platform, comments vs saves.)
5. What is transferable to us **this month**, at our budget?

Answers land in the SWOT block *and* as swipe-file entries. An audit that produces no swipe
entry is an audit that wasn't done.

## Strategic gap analysis

Contrast the target artist against the **tier-matched, subgenre-matched** peer median — never
the peer maximum.

For each dimension, record: our value, peer median, delta, and a single next action.

Dimensions tracked in `data/`:

- monthly listeners, Boomplay streams
- short-form posts/week, median views
- DJ spins confirmed (30d), radio adds (30d)
- editorial playlist adds (90d)
- WhatsApp list size, live shows (90d)
- cross-border listener share

Rules of interpretation:

- **Deficit on a dimension the peers win on** → copy the mechanism, not the content.
- **Surplus on a dimension peers ignore** → that is the wedge; over-invest there.
- **Deficit everywhere** → the tier is wrong. Re-run Phase 2 before spending anything.

Run it:

```bash
python3 scripts/chartmeter.py gaps
```

## Pivot criteria

Change the campaign only when one of these fires — otherwise, hold and let the loop run:

- A format hits ≥3× the median views twice in a row → scale it to 4 posts/week.
- DJ spins flat for 21 days after a full seeding cycle → the record is not a club record; pivot to sync/playlist/feature.
- Editorial adds = 0 after two releases while peer median ≥2 → fix metadata, pitch lead time, and pre-save volume before blaming the music.
- WhatsApp reply rate <5% → the broadcasts are announcements, not conversations; rewrite as voice notes.

## Definition of done for a release cycle

- [ ] Baseline updated and dated
- [ ] Peer set re-verified against the Phase 2 checklist
- [ ] DJ pack shipped to all three tiers in all three markets
- [ ] ≥1 cross-border touchpoint (feature, remix, or co-hosted live)
- [ ] ≥10 swipe entries captured during the cycle
- [ ] Gap report generated and the next single action chosen per dimension
