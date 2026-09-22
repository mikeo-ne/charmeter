#!/usr/bin/env python3
"""Chartmeter // East Africa Intelligence Hub — CLI.

Validates the Chartmeter data files, groups competitors by career tier, and runs
strategic gap analysis against the tier- and subgenre-matched peer median.

Usage:
    python3 scripts/chartmeter.py validate
    python3 scripts/chartmeter.py tiers
    python3 scripts/chartmeter.py gaps
    python3 scripts/chartmeter.py radar
    python3 scripts/chartmeter.py swipe
    python3 scripts/chartmeter.py report

Dependency-free: ships a parser for the restricted YAML subset documented in
docs/05-data-schemas.md.
"""

from __future__ import annotations

import datetime as _dt
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

TIERS = {
    "upcoming": (0, 20_000),
    "mid": (20_000, 500_000),
    "aspirational": (500_000, float("inf")),
}

TIER_LABEL = {
    "upcoming": "Upcoming Tier (0-20k listeners)",
    "mid": "Mid-Level Tier (20k-500k listeners)",
    "aspirational": "Aspirational (tactics only, never a benchmark)",
}

METRICS = [
    ("monthly_listeners", "Monthly listeners"),
    ("boomplay_streams", "Boomplay streams"),
    ("shortform_posts_per_week", "Short-form posts/week"),
    ("shortform_median_views", "Short-form median views"),
    ("dj_spins_30d", "DJ spins (30d)"),
    ("radio_adds_30d", "Radio adds (30d)"),
    ("editorial_playlist_adds_90d", "Editorial adds (90d)"),
    ("whatsapp_list_size", "WhatsApp list size"),
    ("live_shows_90d", "Live shows (90d)"),
    ("crossborder_listener_share", "Cross-border share"),
]

ACTIONS = {
    "monthly_listeners": "Lift the top-of-funnel: pitch playlists and run a seeded short-form push.",
    "boomplay_streams": "Fix the Boomplay artist page and run a Boomplay-first release week.",
    "shortform_posts_per_week": "Raise cadence to the peer median before changing the creative.",
    "shortform_median_views": "Copy the peers' best-performing mechanic, not their content.",
    "dj_spins_30d": "Run a full 3-tier DJ seeding cycle (docs/03-regional-playbook.md).",
    "radio_adds_30d": "Pitch 5 stations with a dated pack and a crowd-reaction clip as proof.",
    "editorial_playlist_adds_90d": "Fix metadata and pitch 4 weeks ahead of release.",
    "whatsapp_list_size": "Convert every live room and event to the broadcast list via a short link.",
    "live_shows_90d": "Trade two free songs for guest lists at campus and underground nights.",
    "crossborder_listener_share": "Book one cross-border feature or co-hosted live this cycle.",
}

VALID_CLASSES = {"fm", "dj", "tastemaker", "promo-network"}
VALID_CHANNELS = {"tiktok", "instagram", "whatsapp", "youtube", "radio"}


# --------------------------------------------------------------------------- YAML subset

def _split_flow(body: str):
    """Split 'a: 1, b: {c: 2}' on top-level commas only."""
    parts, depth, cur, quote = [], 0, "", None
    for ch in body:
        if quote:
            cur += ch
            if ch == quote:
                quote = None
            continue
        if ch in "'\"":
            quote = ch
            cur += ch
        elif ch in "{[":
            depth += 1
            cur += ch
        elif ch in "}]":
            depth -= 1
            cur += ch
        elif ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur)
    return parts


def _scalar(text: str):
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
        return text[1:-1]
    # Inline flow mapping: {a: 1, b: two}
    if text.startswith("{") and text.endswith("}"):
        out = {}
        for part in _split_flow(text[1:-1]):
            if ":" not in part:
                continue
            k, _, v = part.partition(":")
            out[k.strip().strip("'\"")] = _scalar(v)
        return out
    # Inline flow sequence: [a, b, c]
    if text.startswith("[") and text.endswith("]"):
        return [_scalar(p) for p in _split_flow(text[1:-1]) if p.strip()]
    low = text.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("null", "~", ""):
        return None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text


def parse_yaml(text: str):
    """Parse the restricted subset: nested maps and lists of maps/scalars."""
    lines = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        lines.append((len(raw) - len(raw.lstrip(" ")), raw.strip()))

    def block(idx: int, indent: int):
        if idx < len(lines) and lines[idx][1].startswith("- "):
            return seq(idx, indent)
        return mapping(idx, indent)

    def mapping(idx: int, indent: int):
        out = {}
        while idx < len(lines):
            ind, content = lines[idx]
            if ind < indent or content.startswith("- "):
                break
            key, _, rest = content.partition(":")
            key = key.strip()
            rest = rest.strip()
            if rest:
                out[key] = _scalar(rest)
                idx += 1
            else:
                idx += 1
                if idx < len(lines) and lines[idx][0] > ind:
                    out[key], idx = block(idx, lines[idx][0])
                else:
                    out[key] = None
        return out, idx

    def seq(idx: int, indent: int):
        out = []
        while idx < len(lines):
            ind, content = lines[idx]
            if ind != indent or not content.startswith("- "):
                break
            item = content[2:].strip()
            if ":" in item and not item.endswith(":"):
                key, _, rest = item.partition(":")
                entry = {key.strip(): _scalar(rest)}
                idx += 1
                while idx < len(lines) and lines[idx][0] > indent and not lines[idx][1].startswith("- "):
                    sub, idx = mapping(idx, lines[idx][0])
                    entry.update(sub)
                out.append(entry)
            elif item.endswith(":"):
                key = item[:-1].strip()
                idx += 1
                val, idx = block(idx, lines[idx][0]) if idx < len(lines) and lines[idx][0] > indent else (None, idx)
                out.append({key: val})
            else:
                out.append(_scalar(item))
                idx += 1
        return out, idx

    result, _ = block(0, lines[0][0]) if lines else ({}, 0)
    return result


def load(filename: str):
    path = os.path.join(DATA, filename)
    if not os.path.exists(path):
        sys.exit("missing data file: %s" % path)
    with open(path, encoding="utf-8") as fh:
        return parse_yaml(fh.read())


def load_all():
    return (
        load("artist-baseline.yml"),
        load("competitors.yml").get("competitors") or [],
        load("radar.yml").get("contacts") or [],
        load("swipe-file.yml").get("entries") or [],
    )


# --------------------------------------------------------------------------- helpers

def tier_for(listeners) -> str:
    for name, (lo, hi) in TIERS.items():
        if lo <= (listeners or 0) < hi:
            return name
    return "aspirational"


def days_since(datestr) -> int | None:
    try:
        d = _dt.date.fromisoformat(str(datestr))
    except (TypeError, ValueError):
        return None
    return (_dt.date.today() - d).days


def fmt(key: str, value) -> str:
    if value is None:
        return "-"
    if key == "crossborder_listener_share":
        return "%.0f%%" % (value * 100)
    if isinstance(value, int):
        return "{:,}".format(value)
    return str(value)


def peers(artist, competitors):
    """Tier- and subgenre-matched peer set — the only valid benchmark."""
    return [
        c for c in competitors
        if c.get("tier") == artist.get("tier")
        and c.get("subgenre") == artist.get("subgenre")
    ]


# --------------------------------------------------------------------------- commands

def cmd_validate(artist, competitors, radar, swipe) -> int:
    errors, warnings = [], []

    if not artist.get("name"):
        errors.append("baseline: missing name")
    if artist.get("tier") not in TIERS:
        errors.append("baseline: tier must be one of %s" % ", ".join(TIERS))
    stale = days_since(artist.get("last_audit"))
    if stale is None:
        errors.append("baseline: last_audit missing or not YYYY-MM-DD")
    elif stale > 45:
        warnings.append("baseline: last audit is %d days old (>45)" % stale)

    ml = (artist.get("metrics") or {}).get("monthly_listeners")
    if ml is not None and tier_for(ml) != artist.get("tier"):
        errors.append(
            "baseline: tier '%s' disagrees with %s monthly listeners (expected '%s')"
            % (artist.get("tier"), fmt("monthly_listeners", ml), tier_for(ml))
        )

    names = set()
    for c in competitors:
        n = c.get("name", "<unnamed>")
        if n in names:
            errors.append("competitors: duplicate entry '%s'" % n)
        names.add(n)
        m = c.get("metrics") or {}
        if c.get("tier") not in TIERS:
            errors.append("%s: invalid tier '%s'" % (n, c.get("tier")))
        elif tier_for(m.get("monthly_listeners")) != c.get("tier"):
            errors.append(
                "%s: tier '%s' disagrees with %s monthly listeners (expected '%s')"
                % (n, c.get("tier"), fmt("monthly_listeners", m.get("monthly_listeners")),
                   tier_for(m.get("monthly_listeners")))
            )
        if not c.get("active_last_120d"):
            warnings.append("%s: not active in last 120d — fails Phase 2 admission" % n)
        for field in ("visual_hooks", "performance_loop", "dropoff"):
            if not c.get(field):
                warnings.append("%s: SWOT field '%s' empty" % (n, field))
        age = days_since(c.get("last_audit"))
        if age is None:
            errors.append("%s: last_audit missing or malformed — undated SWOT is expired" % n)
        elif age > 45:
            warnings.append("%s: SWOT is %d days old (>45)" % (n, age))
        for key, _ in METRICS:
            if m.get(key) is None:
                warnings.append("%s: metric '%s' missing" % (n, key))

    if not peers(artist, competitors):
        warnings.append(
            "no tier+subgenre matched peers for %s (%s / %s) — gap analysis will be empty"
            % (artist.get("name"), artist.get("tier"), artist.get("subgenre"))
        )

    for c in radar:
        n = c.get("name", "<unnamed>")
        if c.get("class") not in VALID_CLASSES:
            errors.append("radar '%s': class must be one of %s" % (n, ", ".join(sorted(VALID_CLASSES))))
        if not c.get("outcome"):
            errors.append("radar '%s': outcome required before re-contact" % n)
        if days_since(c.get("last_contact")) is None:
            errors.append("radar '%s': last_contact missing or malformed" % n)

    for e in swipe:
        label = "%s/%s" % (e.get("source", "?"), e.get("channel", "?"))
        if e.get("channel") not in VALID_CHANNELS:
            errors.append("swipe '%s': channel must be one of %s" % (label, ", ".join(sorted(VALID_CHANNELS))))
        if not e.get("principle"):
            errors.append("swipe '%s': missing transferable principle — delete or complete" % label)

    print("# Validation\n")
    for e in errors:
        print("ERROR   %s" % e)
    for w in warnings:
        print("WARN    %s" % w)
    print("\n%d error(s), %d warning(s) across %d competitors, %d radar contacts, %d swipe entries."
          % (len(errors), len(warnings), len(competitors), len(radar), len(swipe)))
    return 1 if errors else 0


def cmd_tiers(artist, competitors, *_):
    print("# Tiered Competitor Matrix\n")
    print("Target: **%s** — %s / %s (%s)\n"
          % (artist.get("name"), artist.get("subgenre"), artist.get("tier"),
             fmt("monthly_listeners", (artist.get("metrics") or {}).get("monthly_listeners"))))
    for tier in ("upcoming", "mid", "aspirational"):
        group = [c for c in competitors if c.get("tier") == tier]
        if not group:
            continue
        print("## %s\n" % TIER_LABEL[tier])
        print("| Competitor | Subgenre | Market | Listeners | Boomplay | DJ spins 30d | Editorial 90d | Peer? |")
        print("|---|---|---|---|---|---|---|---|")
        for c in sorted(group, key=lambda x: -((x.get("metrics") or {}).get("monthly_listeners") or 0)):
            m = c.get("metrics") or {}
            is_peer = "yes" if (c.get("subgenre") == artist.get("subgenre")
                                and c.get("tier") == artist.get("tier")) else "tactics only"
            print("| %s | %s | %s, %s | %s | %s | %s | %s | %s |" % (
                c.get("name"), c.get("subgenre"), c.get("city"), c.get("country"),
                fmt("monthly_listeners", m.get("monthly_listeners")),
                fmt("boomplay_streams", m.get("boomplay_streams")),
                fmt("dj_spins_30d", m.get("dj_spins_30d")),
                fmt("editorial_playlist_adds_90d", m.get("editorial_playlist_adds_90d")),
                is_peer))
        print()
    return 0


def cmd_gaps(artist, competitors, *_):
    ps = peers(artist, competitors)
    print("# Strategic Gap Analysis\n")
    print("Target: **%s** (%s / %s)  ·  Peer set: %d tier+subgenre matched acts\n"
          % (artist.get("name"), artist.get("subgenre"), artist.get("tier"), len(ps)))
    if not ps:
        print("No matched peers. Re-run Phase 2 (docs/02-tiered-filtering.md) before spending anything.")
        return 0
    print("Peers: %s\n" % ", ".join(c.get("name") for c in ps))

    am = artist.get("metrics") or {}
    deficits, surpluses = [], []
    print("| Dimension | Us | Peer median | Delta | Read |")
    print("|---|---|---|---|---|")
    for key, label in METRICS:
        vals = [(c.get("metrics") or {}).get(key) for c in ps]
        vals = [v for v in vals if v is not None]
        ours = am.get(key)
        if not vals or ours is None:
            print("| %s | %s | - | - | insufficient data |" % (label, fmt(key, ours)))
            continue
        med = statistics.median(vals)
        delta = ours - med
        pct = (delta / med * 100) if med else float("inf")
        read = "surplus — wedge" if delta > 0 else ("parity" if delta == 0 else "deficit")
        if delta < 0:
            deficits.append((key, label, ours, med, pct))
        elif delta > 0:
            surpluses.append((label, pct))
        delta_s = "-" if med == 0 and delta == 0 else ("%+.0f%%" % pct if med else "n/a")
        print("| %s | %s | %s | %s | %s |" % (
            label, fmt(key, ours), fmt(key, round(med, 4) if isinstance(med, float) else med),
            delta_s, read))

    print("\n## Deficits — highest leverage first\n")
    for key, label, ours, med, pct in sorted(deficits, key=lambda x: x[4]):
        print("- **%s** (%s vs peer median %s, %+.0f%%) → %s"
              % (label, fmt(key, ours), fmt(key, round(med, 4) if isinstance(med, float) else med),
                 pct, ACTIONS.get(key, "Investigate.")))
    if not deficits:
        print("- None. Consider re-tiering upward.")

    print("\n## Surpluses — over-invest here\n")
    for label, pct in sorted(surpluses, key=lambda x: -x[1]):
        print("- **%s** (%+.0f%% vs peers) — this is the wedge; scale it before fixing anything else." % (label, pct))
    if not surpluses:
        print("- None yet. Pick one dimension peers ignore and manufacture a surplus.")

    if len(deficits) == len([m for m in METRICS if am.get(m[0]) is not None]):
        print("\n> Deficit on every dimension — the tier is probably wrong. Re-run Phase 2 before spending.")
    return 0


def cmd_radar(artist, competitors, radar, *_):
    print("# Media, DJ & Radio Radar\n")
    by_city = {}
    for c in radar:
        by_city.setdefault(c.get("city", "Unknown"), []).append(c)
    for city in sorted(by_city):
        print("## %s\n" % city)
        print("| Contact | Class | Genre lean | Route | Last contact | Days | Outcome |")
        print("|---|---|---|---|---|---|---|")
        for c in sorted(by_city[city], key=lambda x: x.get("class", "")):
            d = days_since(c.get("last_contact"))
            print("| %s | %s | %s | %s | %s | %s | %s |" % (
                c.get("name"), c.get("class"), c.get("genre_lean"),
                c.get("submission_route"), c.get("last_contact"),
                d if d is not None else "-", c.get("outcome")))
        print()
    cold = [c for c in radar if (days_since(c.get("last_contact")) or 0) > 30]
    if cold:
        print("**Going cold (>30 days):** %s" % ", ".join(c.get("name") for c in cold))
    return 0


def cmd_swipe(artist, competitors, radar, swipe):
    print("# Swipe File\n")
    by_channel = {}
    for e in swipe:
        by_channel.setdefault(e.get("channel", "other"), []).append(e)
    for ch in sorted(by_channel):
        print("## %s\n" % ch)
        for e in sorted(by_channel[ch], key=lambda x: str(x.get("date")), reverse=True):
            print("- **%s** (%s) — %s" % (e.get("source"), e.get("date"), e.get("hook")))
            print("  - Format: %s  ·  Metrics: %s" % (e.get("format"), e.get("metrics")))
            print("  - *Principle:* %s" % e.get("principle"))
        print()
    return 0


def cmd_report(artist, competitors, radar, swipe):
    print("# Chartmeter // East Africa Intelligence Hub — Report")
    print("\nGenerated %s  ·  Target artist: **%s** (%s, %s)\n"
          % (_dt.date.today().isoformat(), artist.get("name"),
             artist.get("city"), artist.get("country")))
    print("---\n")
    cmd_tiers(artist, competitors)
    print("---\n")
    cmd_gaps(artist, competitors)
    print("\n---\n")
    cmd_radar(artist, competitors, radar)
    print("---\n")
    cmd_swipe(artist, competitors, radar, swipe)
    return 0


COMMANDS = {
    "validate": cmd_validate,
    "tiers": cmd_tiers,
    "gaps": cmd_gaps,
    "radar": cmd_radar,
    "swipe": cmd_swipe,
    "report": cmd_report,
}


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "report"
    if cmd in ("-h", "--help", "help") or cmd not in COMMANDS:
        print(__doc__)
        return 0 if cmd in ("-h", "--help", "help") else 2
    return COMMANDS[cmd](*load_all())


if __name__ == "__main__":
    sys.exit(main(sys.argv))
