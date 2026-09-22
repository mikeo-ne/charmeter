#!/usr/bin/env python3
"""Fetch platform stats and write them into the Chartmeter data files.

So you stop typing numbers in by hand.

Usage:
    python3 scripts/fetch_stats.py --check            # which providers are configured
    python3 scripts/fetch_stats.py --dry-run          # fetch + show diff, write nothing
    python3 scripts/fetch_stats.py                    # fetch + update data files
    python3 scripts/fetch_stats.py --only boomplay,youtube
    python3 scripts/fetch_stats.py --artist Nsimbi
    python3 scripts/fetch_stats.py --history          # also append to data/history.csv

Credentials come from the environment (or a local .env file, gitignored):
    BOOMPLAY_APP_ID / BOOMPLAY_APP_SECRET
    YOUTUBE_API_KEY
    LASTFM_API_KEY
    SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET

Metrics no API can supply (DJ spins, monthly listeners, WhatsApp list, ...)
are never touched by this script - see docs/06-data-sources.md.
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import providers  # noqa: E402
from chartmeter import load, parse_yaml  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")


def load_dotenv() -> None:
    path = os.path.join(ROOT, ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


# --------------------------------------------------------------- surgical YAML editing

def set_metric(path: str, artist: str, key: str, value) -> bool:
    """Update `key` under the `metrics:` block of `artist` in a data file.

    Edits the line in place so comments, ordering and formatting survive -
    a full re-serialise would destroy the hand-written notes in these files.
    Returns True if the file changed.
    """
    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()

    # locate the artist block
    start = None
    for i, line in enumerate(lines):
        if re.match(r"^\s*-?\s*name:\s*%s\s*$" % re.escape(artist), line):
            start = i
            break
    if start is None:
        return False

    # find the following `metrics:` block and its end
    m_start = None
    for i in range(start + 1, len(lines)):
        if re.match(r"^\s*-\s*name:", lines[i]):
            break
        if re.match(r"^\s*metrics:\s*$", lines[i]):
            m_start = i
            break
    if m_start is None:
        return False

    indent = len(lines[m_start]) - len(lines[m_start].lstrip())
    m_end = len(lines)
    for i in range(m_start + 1, len(lines)):
        stripped = lines[i].strip()
        if not stripped or stripped.startswith("#"):
            continue
        if (len(lines[i]) - len(lines[i].lstrip())) <= indent:
            m_end = i
            break
    # Don't append after trailing blank lines - back up to the last real entry.
    while m_end - 1 > m_start and not lines[m_end - 1].strip():
        m_end -= 1

    child_indent = " " * (indent + 2)
    new_line = "%s%s: %s\n" % (child_indent, key, value)

    for i in range(m_start + 1, m_end):
        if re.match(r"^\s*%s:" % re.escape(key), lines[i]):
            if lines[i] == new_line:
                return False
            lines[i] = new_line
            break
    else:
        lines.insert(m_end, new_line)

    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(lines)
    return True


# --------------------------------------------------------------------------- runner

def build_targets(sources, baseline, competitors, only_artist):
    by_name = {baseline.get("name"): ("artist-baseline.yml", baseline)}
    for c in competitors:
        by_name[c.get("name")] = ("competitors.yml", c)

    targets = []
    for entry in sources.get("artists") or []:
        name = entry.get("name")
        if only_artist and name != only_artist:
            continue
        if name not in by_name:
            print("  ! '%s' in sources.yml matches no artist or competitor - skipped" % name)
            continue
        targets.append((name, by_name[name][0], entry))
    return targets


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="show provider credential status and exit")
    ap.add_argument("--dry-run", action="store_true", help="fetch and diff, write nothing")
    ap.add_argument("--only", default="", help="comma-separated provider names")
    ap.add_argument("--artist", default="", help="limit to one artist/competitor name")
    ap.add_argument("--history", action="store_true", help="append results to data/history.csv")
    args = ap.parse_args()

    load_dotenv()

    wanted = [p.strip() for p in args.only.split(",") if p.strip()] or list(providers.REGISTRY)
    unknown = [p for p in wanted if p not in providers.REGISTRY]
    if unknown:
        print("unknown provider(s): %s" % ", ".join(unknown))
        print("available: %s" % ", ".join(providers.REGISTRY))
        return 2

    if args.check:
        print("# Provider status\n")
        print("| Provider | Credentials | Metrics | Notes |")
        print("|---|---|---|---|")
        for name in providers.REGISTRY:
            p = providers.get(name)
            status = "ready" if p.available() else ("MISSING " + ",".join(p.missing()))
            print("| %s | %s | %s | %s |" % (name, status, ", ".join(p.METRICS), p.NOTE))
        print("\n# Manual-only metrics (no API provides these)\n")
        for k, why in providers.MANUAL_ONLY.items():
            print("- %-32s %s" % (k, why))
        return 0

    sources = load("sources.yml")
    baseline = load("artist-baseline.yml")
    competitors = load("competitors.yml").get("competitors") or []
    targets = build_targets(sources, baseline, competitors, args.artist)

    if not targets:
        print("No targets. Add ids to data/sources.yml.")
        return 1

    active = []
    for name in wanted:
        p = providers.get(name)
        if p.available():
            active.append(p)
        else:
            print("skip %-12s missing %s" % (name, ", ".join(p.missing())))
    if not active:
        print("\nNo providers configured. Run --check, then set credentials in .env")
        return 1

    print("\nProviders: %s" % ", ".join(p.NAME for p in active))
    print("Targets:   %d\n" % len(targets))

    today = _dt.date.today().isoformat()
    changes, failures, history_rows = [], [], []

    for name, filename, ids in targets:
        print("%s" % name)
        for p in active:
            ident = str(ids.get(p.NAME) or "").strip()
            if not ident:
                continue
            try:
                result = p.fetch(ident)
            except providers.ProviderError as exc:
                print("   %-12s FAILED %s" % (p.NAME, exc))
                failures.append((name, p.NAME, str(exc)))
                continue
            except Exception as exc:  # noqa: BLE001 - never let one provider kill the run
                print("   %-12s ERROR  %s" % (p.NAME, exc))
                failures.append((name, p.NAME, repr(exc)))
                continue

            for key, value in sorted(result.items()):
                if key.startswith("_"):
                    continue
                if key in providers.MANUAL_ONLY:
                    continue  # never auto-write a manual-only field
                path = os.path.join(DATA, filename)
                if args.dry_run:
                    print("   %-12s %s = %s (dry-run)" % (p.NAME, key, value))
                    changes.append((name, key, value))
                else:
                    if set_metric(path, name, key, value):
                        print("   %-12s %s = %s  updated" % (p.NAME, key, value))
                        changes.append((name, key, value))
                    else:
                        print("   %-12s %s = %s  unchanged" % (p.NAME, key, value))
                history_rows.append((today, name, p.NAME, key, value))

        if not args.dry_run:
            set_metric(os.path.join(DATA, filename), name, "_fetched", today)

    if args.history and history_rows and not args.dry_run:
        hist = os.path.join(DATA, "history.csv")
        new = not os.path.exists(hist)
        with open(hist, "a", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            if new:
                w.writerow(["date", "artist", "provider", "metric", "value"])
            w.writerows(history_rows)
        print("\nAppended %d rows to data/history.csv" % len(history_rows))

    print("\n%s: %d metric(s) %s, %d failure(s)." % (
        "Dry run" if args.dry_run else "Done",
        len(changes), "would change" if args.dry_run else "written", len(failures)))
    if not args.dry_run and changes:
        print("Next: python3 scripts/chartmeter.py validate && python3 scripts/chartmeter.py gaps")
    return 0


if __name__ == "__main__":
    sys.exit(main())
