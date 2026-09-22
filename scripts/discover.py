#!/usr/bin/env python3
"""Suggest competitors from the user's own stats.

Applies the Phase 2 rules (docs/02-tiered-filtering.md) to a candidate pool and
scores each act by how useful a benchmark it is for *this* artist:

  * Hard filters  - exact subgenre, same career tier, active in last 120 days.
  * Proximity     - closeness in monthly listeners; an act at 3x your size is a
                    worse benchmark than one at 1.2x, even inside the same tier.
  * Market bonus  - same country, or a target cross-border market.

The pool ships in data/candidates.yml as a starter directory. It is seed data,
not a live index: the honest framing is "shortlist to verify", not "truth".
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import chartmeter as cm  # noqa: E402

NEIGHBOURS = {"UG": {"KE", "TZ", "RW"}, "KE": {"UG", "TZ"}, "TZ": {"KE", "UG"}}


def load_pool() -> list:
    try:
        return cm.load("candidates.yml").get("candidates") or []
    except SystemExit:
        return []


def suggest(artist: dict, existing: list, pool: list | None = None, limit: int = 12) -> dict:
    """-> {'suggestions': [...], 'rejected': [...], 'reason': str|None}"""
    pool = pool if pool is not None else load_pool()
    metrics = artist.get("metrics") or {}
    ours = metrics.get("monthly_listeners")
    subgenre = (artist.get("subgenre") or "").strip()
    country = (artist.get("country") or "").strip().upper()

    if not subgenre:
        return {"suggestions": [], "rejected": [],
                "reason": "Set your subgenre first — benchmarking only works "
                          "against acts in the same exact subgenre."}
    if not isinstance(ours, (int, float)):
        return {"suggestions": [], "rejected": [],
                "reason": "Add your monthly listeners first — the peer tier is "
                          "derived from it."}

    tier = cm.tier_for(ours)
    have = {c.get("name") for c in (existing or [])}
    suggestions, rejected = [], []

    for cand in pool:
        name = cand.get("name")
        if not name or name in have or name == artist.get("name"):
            continue
        cm_metrics = cand.get("metrics") or {}
        cl = cm_metrics.get("monthly_listeners")

        if (cand.get("subgenre") or "").strip() != subgenre:
            rejected.append({"name": name, "why": "different subgenre (%s)" % cand.get("subgenre")})
            continue
        if not isinstance(cl, (int, float)):
            rejected.append({"name": name, "why": "no listener data"})
            continue
        if cm.tier_for(cl) != tier:
            rejected.append({"name": name, "why": "different tier (%s)" % cm.tier_for(cl)})
            continue
        if cand.get("active_last_120d") is False:
            rejected.append({"name": name, "why": "inactive in last 120 days"})
            continue

        # Proximity: 100 when identical size, decaying with the ratio.
        bigger, smaller = max(cl, ours), min(cl, ours)
        ratio = bigger / smaller if smaller else 99.0
        proximity = max(0.0, 100.0 - (ratio - 1.0) * 55.0)

        cc = (cand.get("country") or "").upper()
        if cc == country:
            market, market_note = 18.0, "same market"
        elif cc in NEIGHBOURS.get(country, set()):
            market, market_note = 11.0, "cross-border target"
        else:
            market, market_note = 0.0, "outside target markets"

        score = round(min(100.0, proximity * 0.82 + market), 1)
        suggestions.append({
            "name": name,
            "country": cand.get("country"),
            "city": cand.get("city"),
            "subgenre": cand.get("subgenre"),
            "tier": cm.tier_for(cl),
            "metrics": cm_metrics,
            "links": cand.get("links") or {},
            "score": score,
            "ratio": round(ratio, 2),
            "why": "%s listeners vs your %s (%.1fx) · %s"
                   % (format(int(cl), ","), format(int(ours), ","), ratio, market_note),
        })

    suggestions.sort(key=lambda s: -s["score"])
    return {
        "suggestions": suggestions[:limit],
        "rejected": rejected,
        "tier": tier,
        "subgenre": subgenre,
        "reason": None if suggestions else
                  "No candidates match %s in the %s tier. Add competitors manually, "
                  "or widen the directory in data/candidates.yml." % (subgenre, tier),
    }
