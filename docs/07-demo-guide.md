# Running a Client Demo

The web app turns Chartmeter from a documented method into something a client can
click through in ten minutes.

```bash
python3 scripts/server.py --port 3000
# open http://localhost:3000
```

Flags: `--reset` re-seeds the demo data on start, `--host`/`--port` to change binding.
No dependencies, no build step.

---

## Before the client arrives

```bash
python3 scripts/server.py --port 3000 --reset
```

`--reset` guarantees a clean, predictable dataset. Edits made during a demo live in
`data/workspace.json`, which is **gitignored and never written back to `data/*.yml`** —
so you can let a prospect add and delete competitors freely and the repo stays pristine.
The **Reset demo data** button in the sidebar restores the seed mid-conversation.

Optional: swap the seed in `data/artist-baseline.yml` and `data/competitors.yml` for
the client's own act and three or four of their real rivals before you start. A demo
with their own name in it closes considerably better than one about "Nsimbi".

---

## The ten-minute script

**1. Overview — "here is where you stand" (90 seconds)**

Lead with the competitive health ring. It is a single number for *what share of your
dimensions sit at or above the peer median*. Then the two panels beneath it:
highest-leverage deficits and the wedge.

The point to make: this is not a dashboard of vanity metrics, it is a ranked list of
what to do next.

**2. Gap Analysis — the credibility moment (3 minutes)**

This is the page that sells the system. Two things to say out loud:

- *"You are compared against the **median** of your peer set, never the best act in it."*
  One outlier should not set anyone's targets.
- *"Only acts in your exact tier **and** your exact subgenre are in that median."*
  A Luganda-pop artist at 7k listeners is not measured against a Tanzanian act at 145k.

Then point at a deficit row and read the **Next action** column. Every gap resolves to
a concrete move, not an observation.

**3. Competitor Matrix — let them drive (3 minutes)**

Hand over the laptop. Ask them to add a rival they care about.

Two behaviours to make sure they see:

- Leave **Tier** on *auto* — it derives from monthly listeners, so nobody can
  mis-file a competitor.
- Try to add an act at, say, 90,000 listeners and force the tier to *Upcoming*. The
  app **refuses** and explains why. That refusal is the product: the methodology is
  enforced, not merely suggested.

Notice the **Role** column — acts outside their tier/subgenre are marked *tactics only*
and are silently excluded from the gap median.

**4. Radar — "this is the part nobody automates" (90 seconds)**

A DJ and radio CRM across Kampala, Nairobi and Dar. Highlight the **cold** flags: any
contact untouched for 30+ days. Rule to state: *no contact is approached twice without
an outcome logged.*

**5. Data Sources — the honesty slide (2 minutes)**

Counter-intuitively, the strongest page in the deck.

Say plainly: **Spotify monthly listeners cannot be fetched from any official API** —
extended access requires 250,000+ monthly active users, which excludes every
independent artist. Chartmeter refuses to scrape it.

Then: Boomplay, YouTube, Last.fm and MusicBrainz *do* update themselves, and the
metrics that stay manual — DJ spins, WhatsApp list size, radio adds — are precisely
the highest-signal numbers in this market and the ones no platform will ever sell you.

Clients have been pitched scraped dashboards before. Being specific about what is
impossible is what makes the rest of the numbers believable.

---

## Questions you will get

**"Where does the data come from?"**
Boomplay's official OpenAPI, YouTube Data API v3, Last.fm and MusicBrainz, on a
monthly scheduled job. Fieldwork metrics are entered by the analyst. The Data Sources
page lists every field and its origin.

**"Can it track my own artist?"**
Yes — one YAML file, or the API. Setup is about fifteen minutes once platform IDs are known.

**"Why so few competitors?"**
Deliberate. Eight to twelve tier-matched peers is the useful range; beyond that the
median stops moving and the analysis gets noisier, not sharper.

**"Is the demo data real?"**
No — say so immediately. The seed artist and rivals are illustrative placeholders
built to exercise the system. Offer to rebuild it with their real peer set as the
first deliverable.

---

## Architecture, if they ask

- `scripts/server.py` — stdlib HTTP server, JSON API, no framework.
- `webapp/` — vanilla JS single-page front end, no build step.
- Analysis is imported from `scripts/chartmeter.py`, so the website and the CLI are
  mathematically identical. Verify live in front of them:

  ```bash
  python3 scripts/chartmeter.py gaps
  ```

  Same peer set, same medians, same deltas as the browser.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/overview` | Baseline, counts, health score, top deficits |
| GET | `/api/gaps` | Full gap analysis vs peer median |
| GET | `/api/competitors` | Matrix + metric definitions |
| GET | `/api/radar` | DJ/radio CRM with cold flags |
| GET | `/api/swipe` | Swipe file entries |
| GET | `/api/providers` | Connector status + manual-only fields |
| POST | `/api/competitors` | Add (validates tier vs listeners) |
| DELETE | `/api/competitors/<name>` | Remove |
| POST | `/api/artist` | Update baseline |
| POST | `/api/reset` | Re-seed demo data |

## Deploying for remote demos

The app is a long-running process, so GitHub Pages (static) cannot host it. Any small
VM or container works:

```bash
python3 scripts/server.py --host 0.0.0.0 --port 8080
```

Put it behind a reverse proxy with TLS for anything client-facing. The static docs site
(`scripts/build_site.py`) remains the right choice for the public-facing methodology.
