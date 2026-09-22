#!/usr/bin/env python3
"""Derived intelligence: CPP-style score, automatic SWOT, and campaign plans.

Everything here is computed from the artist's own metrics against their
tier- and subgenre-matched peer set. Nothing is invented: every SWOT line and
every campaign action cites the number that triggered it, so a client can
always ask "why does it say that?" and get a concrete answer.
"""

from __future__ import annotations

import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import chartmeter as cm  # noqa: E402

# Cross-Platform Performance weighting. Reach (audience size) is weighted
# below Traction (things that indicate active demand), because in this market
# a big follower count with no DJ rotation is a vanity number.
CPP_WEIGHTS = {
    "monthly_listeners": ("reach", 1.4),
    "boomplay_streams": ("reach", 1.6),
    "youtube_subscribers": ("reach", 0.8),
    "shortform_median_views": ("traction", 1.5),
    "shortform_posts_per_week": ("traction", 0.7),
    "dj_spins_30d": ("traction", 1.8),
    "radio_adds_30d": ("traction", 1.0),
    "editorial_playlist_adds_90d": ("traction", 1.2),
    "whatsapp_list_size": ("engagement", 1.3),
    "live_shows_90d": ("engagement", 1.1),
    "crossborder_listener_share": ("engagement", 0.9),
}

LABELS = dict(cm.METRICS)
LABELS.update({
    "youtube_subscribers": "YouTube subscribers",
    "youtube_views": "YouTube views",
    "lastfm_listeners": "Last.fm listeners",
    "spotify_followers": "Spotify followers",
})


def _pct_rank(value, pool) -> float:
    """Percentile of `value` within `pool` (0-100)."""
    if not pool:
        return 50.0
    below = sum(1 for p in pool if p < value)
    same = sum(1 for p in pool if p == value)
    return (below + 0.5 * same) / len(pool) * 100.0


def cpp(artist: dict, peers: list) -> dict:
    """Cross-Platform Performance score: percentile vs peers, 0-100."""
    am = artist.get("metrics") or {}
    cats, detail = {}, []
    for key, (cat, weight) in CPP_WEIGHTS.items():
        ours = am.get(key)
        pool = [(p.get("metrics") or {}).get(key) for p in peers]
        pool = [v for v in pool if isinstance(v, (int, float))]
        if not isinstance(ours, (int, float)) or not pool:
            continue
        rank = _pct_rank(ours, pool)
        cats.setdefault(cat, []).append((rank, weight))
        detail.append({"key": key, "label": LABELS.get(key, key),
                       "percentile": round(rank), "category": cat})

    cat_scores = {}
    for cat, rows in cats.items():
        total_w = sum(w for _, w in rows) or 1
        cat_scores[cat] = round(sum(r * w for r, w in rows) / total_w)

    if cat_scores:
        overall = round(sum(cat_scores.values()) / len(cat_scores))
    else:
        overall = 0

    return {
        "score": overall,
        "categories": cat_scores,
        "detail": sorted(detail, key=lambda d: -d["percentile"]),
        "peer_count": len(peers),
    }


# --------------------------------------------------------------------------- SWOT

# Metrics where a surplus is a genuine strategic asset worth naming.
STRENGTH_NOTES = {
    "dj_spins_30d": "Club rotation is your distribution engine here — protect and extend it.",
    "crossborder_listener_share": "You already travel. That is rare at this tier and is your clearest route up.",
    "whatsapp_list_size": "You own a direct channel that costs nothing to reach and no algorithm can throttle.",
    "shortform_median_views": "Your short-form format is working; it is the cheapest reach you have.",
    "boomplay_streams": "Boomplay is the demand signal that matters most in this region.",
    "live_shows_90d": "A working live circuit converts to DJ relationships and press faster than posting.",
    "editorial_playlist_adds_90d": "Editorial support compounds — curators who add you once add you again.",
    "monthly_listeners": "Your streaming base leads the peer set; convert it to owned contacts.",
    "radio_adds_30d": "Radio presence gives you credibility that unlocks bigger bookings.",
    "shortform_posts_per_week": "Your publishing cadence beats the peer set; keep it and improve the hook.",
}

WEAKNESS_NOTES = {
    "dj_spins_30d": "Without club rotation the record has no street life in this market.",
    "crossborder_listener_share": "You are effectively a one-country act; growth is capped.",
    "whatsapp_list_size": "You have no owned audience — every release restarts from zero.",
    "shortform_median_views": "Your hooks are not landing; this is the cheapest thing to fix.",
    "boomplay_streams": "Weak on the platform where this region's demand shows first.",
    "live_shows_90d": "Too few rooms. Live is where DJ and press relationships actually form.",
    "editorial_playlist_adds_90d": "No editorial support; likely a pitching and metadata problem, not a music problem.",
    "monthly_listeners": "Top-of-funnel is below your peers.",
    "radio_adds_30d": "Radio is not carrying you, which limits reach beyond the internet.",
    "shortform_posts_per_week": "You are not publishing often enough to learn what works.",
}


def swot(artist: dict, peers: list, radar: list | None = None) -> dict:
    """Generate a SWOT automatically from the metric deltas."""
    am = artist.get("metrics") or {}
    radar = radar or []
    strengths, weaknesses, opportunities, threats = [], [], [], []

    for key, label in cm.METRICS:
        ours = am.get(key)
        pool = [(p.get("metrics") or {}).get(key) for p in peers]
        pool = [v for v in pool if isinstance(v, (int, float))]
        if not isinstance(ours, (int, float)) or not pool:
            continue
        med = statistics.median(pool)
        if not med:
            if ours > 0:
                strengths.append({
                    "metric": label, "value": ours, "median": med, "pct": None,
                    "text": "%s: you have %s where the peer median is zero." % (label, _fmt(key, ours)),
                    "note": STRENGTH_NOTES.get(key, ""),
                })
            continue
        delta_pct = (ours - med) / med * 100
        if delta_pct >= 20:
            strengths.append({
                "metric": label, "value": ours, "median": med, "pct": delta_pct,
                "text": "%s is %d%% above the peer median (%s vs %s)."
                        % (label, round(delta_pct), _fmt(key, ours), _fmt(key, med)),
                "note": STRENGTH_NOTES.get(key, ""),
            })
        elif delta_pct <= -20:
            weaknesses.append({
                "metric": label, "value": ours, "median": med, "pct": delta_pct,
                "text": "%s is %d%% below the peer median (%s vs %s)."
                        % (label, round(abs(delta_pct)), _fmt(key, ours), _fmt(key, med)),
                "note": WEAKNESS_NOTES.get(key, ""),
                "action": cm.ACTIONS.get(key, ""),
                "key": key,
            })

    strengths.sort(key=lambda s: -(s["pct"] or 999))
    weaknesses.sort(key=lambda w: w["pct"])

    # ---- Opportunities: gaps in the peer set you could own.
    for key, label in cm.METRICS:
        pool = [(p.get("metrics") or {}).get(key) for p in peers]
        pool = [v for v in pool if isinstance(v, (int, float))]
        if not pool:
            continue
        med = statistics.median(pool)
        ours = am.get(key)
        if med == 0 and (not isinstance(ours, (int, float)) or ours == 0):
            opportunities.append({
                "text": "Nobody in your peer set is doing %s." % label.lower(),
                "note": "An uncontested lane. First mover here defines the category locally.",
                "action": cm.ACTIONS.get(key, ""),
            })

    cold = [c for c in radar if (cm.days_since(c.get("last_contact")) or 0) > 30]
    if cold:
        opportunities.append({
            "text": "%d radar contacts have gone cold (30+ days)." % len(cold),
            "note": "Warm relationships already exist: %s." % ", ".join(
                c.get("name", "") for c in cold[:3]),
            "action": "Re-open with an outcome-led message, not a new ask.",
        })

    share = am.get("crossborder_listener_share")
    if isinstance(share, (int, float)) and share < 0.15:
        opportunities.append({
            "text": "Only %d%% of your audience is outside your home country." % round(share * 100),
            "note": "Kenya and Tanzania are reachable with one well-chosen feature.",
            "action": "Book one cross-border collaboration this cycle.",
        })

    # ---- Threats: peers beating you decisively on a dimension.
    for w in weaknesses[:4]:
        best, best_name = None, None
        for p in peers:
            v = (p.get("metrics") or {}).get(_key_for(w["metric"]))
            if isinstance(v, (int, float)) and (best is None or v > best):
                best, best_name = v, p.get("name")
        if best_name and best and w["value"] is not None and best > w["value"]:
            threats.append({
                "text": "%s leads the peer set on %s (%s vs your %s)."
                        % (best_name, w["metric"].lower(),
                           _fmt(_key_for(w["metric"]), best),
                           _fmt(_key_for(w["metric"]), w["value"])),
                "note": "They are contesting the same DJs, slots and listeners you need.",
            })

    inactive = [p for p in peers if p.get("active_last_120d") is False]
    if inactive:
        opportunities.append({
            "text": "%d peer(s) inactive for 120+ days." % len(inactive),
            "note": "Attention and rotation they held is currently unclaimed.",
            "action": "Push hard into their lane while they are quiet.",
        })

    return {
        "strengths": strengths[:6],
        "weaknesses": weaknesses[:6],
        "opportunities": opportunities[:6],
        "threats": threats[:5],
        "peer_count": len(peers),
        "generated_from": "%d tier- and subgenre-matched peers" % len(peers),
    }


def _key_for(label: str):
    for k, l in cm.METRICS:
        if l == label:
            return k
    return label


def _fmt(key, v):
    if v is None:
        return "—"
    if key == "crossborder_listener_share":
        return "%d%%" % round(v * 100)
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return format(v, ",") if isinstance(v, int) else str(v)


# --------------------------------------------------------------------------- plans

PLAYBOOKS = {
    "dj_spins_30d": {
        "title": "DJ & club saturation",
        "why": "Club rotation is the primary distribution channel in Kampala, Nairobi and Dar.",
        "weeks": [
            ("Week 1", [
                "Build the DJ pack: clean WAV 24-bit, radio MP3 320, instrumental, "
                "personalised 8-bar DJ drop, 3000x3000 art, 60-word bio.",
                "Tier your DJ list: Tier 1 played you before, Tier 2 genre-aligned, "
                "Tier 3 mobile/mixtape and digital mix channels.",
            ]),
            ("Week 2", [
                "Seed Tier 1 by personal voice note with a 5-day exclusive window.",
                "Target 12 Kampala / 8 Nairobi / 6 Dar club DJs.",
            ]),
            ("Week 3", [
                "Seed Tier 2 and 3 with the DJ drop included.",
                "Ask Tier 1 for a crowd-reaction clip, not a repost.",
            ]),
            ("Week 4", [
                "Log every confirmed spin; turn reaction clips into short-form content.",
                "Send the instrumental to mixtape DJs for blends and refixes.",
            ]),
        ],
        "kpi": "Distinct DJs confirmed playing the record in 30 days",
    },
    "shortform_median_views": {
        "title": "Short-form hook rebuild",
        "why": "Your reach per post is below peers — the mechanic is the problem, not the budget.",
        "weeks": [
            ("Week 1", [
                "Audit the 10 best-performing posts from your peer set; log the first 1.5 seconds of each.",
                "Pick ONE repeatable format (street-vox, lyric-reveal, behind-the-decks, fixed-set acoustic).",
            ]),
            ("Week 2", [
                "Shoot a batch of 8 clips in one session using that single format.",
                "Hook must land in the first 1.5 seconds — no intros, no logos.",
            ]),
            ("Week 3", ["Post 4x that week. Same format, same framing, different content."]),
            ("Week 4", [
                "Keep only what beat your median; kill the rest.",
                "Scale the winner to 4 posts/week.",
            ]),
        ],
        "kpi": "Median views per post vs your current median",
    },
    "whatsapp_list_size": {
        "title": "Owned-audience build",
        "why": "WhatsApp is the highest-conversion channel in the region and the least deliberately used.",
        "weeks": [
            ("Week 1", [
                "Create segments: Core-Fans, DJs, Media, Street-Team, Family-Friends.",
                "Put a short link or QR on every live screen, poster and bio.",
            ]),
            ("Week 2", [
                "Convert every room you play into list signups — ask from the stage.",
                "First broadcast: one 30-second voice note, one asset, one tiny ask.",
            ]),
            ("Week 3", ["Ask only: 'post this on your status today.' Nothing else."]),
            ("Week 4", [
                "Measure replies and status reposts, not delivery counts.",
                "If reply rate is under 5%, rewrite as voice notes, not text.",
            ]),
        ],
        "kpi": "List size and reply rate",
    },
    "boomplay_streams": {
        "title": "Boomplay-first release week",
        "why": "Boomplay is where this region's demand appears earliest.",
        "weeks": [
            ("Week 1", ["Claim and complete the Boomplay artist profile: art, bio, socials, all releases."]),
            ("Week 2", ["Pitch the Boomplay editorial team with a dated one-pager and local traction proof."]),
            ("Week 3", ["Drive your WhatsApp list and DJs to Boomplay specifically for release week."]),
            ("Week 4", ["Read per-country play analytics; double down on the country that overperformed."]),
        ],
        "kpi": "Boomplay streams and favourites-to-stream ratio",
    },
    "editorial_playlist_adds_90d": {
        "title": "Editorial pitching system",
        "why": "Zero editorial adds is usually a process failure, not a music failure.",
        "weeks": [
            ("Week 1", ["Fix metadata: correct genre tags, ISRC, clean artwork, complete credits."]),
            ("Week 2", ["Pitch 4 weeks ahead of release through Spotify for Artists and Boomplay."]),
            ("Week 3", ["Build pre-save volume; early saves are the signal curators actually read."]),
            ("Week 4", ["Log which curators respond and re-pitch them next cycle — repeat adders exist."]),
        ],
        "kpi": "Editorial adds per release",
    },
    "crossborder_listener_share": {
        "title": "Cross-border break-in",
        "why": "A feature is a distribution deal disguised as a song.",
        "weeks": [
            ("Week 1", [
                "Shortlist 5 acts in Kenya or Tanzania within one tier of you.",
                "Score on: audience overlap (lower is better), market access, work rate.",
            ]),
            ("Week 2", ["Agree splits, masters, and two named promo obligations each — in writing, before the session."]),
            ("Week 3", ["Record; plan a joint IG live and a radio round in their city."]),
            ("Week 4", ["Release into their market first, then yours."]),
        ],
        "kpi": "Share of listeners outside your home country",
    },
    "radio_adds_30d": {
        "title": "Radio round",
        "why": "Radio still carries credibility that unlocks bookings and press.",
        "weeks": [
            ("Week 1", ["Build the station list with show, presenter, submission route and window."]),
            ("Week 2", ["Send dated packs with a crowd-reaction clip as proof of demand."]),
            ("Week 3", ["Follow up once, by voice note, with a specific outcome ask."]),
            ("Week 4", ["Log every add and rotation level; thank presenters publicly."]),
        ],
        "kpi": "Stations added in 30 days",
    },
    "live_shows_90d": {
        "title": "Room-count push",
        "why": "Live rooms create the DJ and press relationships that content cannot.",
        "weeks": [
            ("Week 1", ["List campus halls, barbershops, car washes, viewing nights, skate and art meet-ups."]),
            ("Week 2", ["Offer two songs free in exchange for the guest list and a filming slot."]),
            ("Week 3", ["Play three rooms; capture audience audio at each."]),
            ("Week 4", ["Convert every room to WhatsApp signups via an on-screen short link."]),
        ],
        "kpi": "Rooms played and list signups per room",
    },
    "monthly_listeners": {
        "title": "Top-of-funnel push",
        "why": "Your streaming base trails the peer set.",
        "weeks": [
            ("Week 1", ["Audit which tracks retain listeners; lead with the strongest, not the newest."]),
            ("Week 2", ["Pitch playlists and run a seeded short-form push behind one track."]),
            ("Week 3", ["Coordinate DJ seeding and content around the same single record."]),
            ("Week 4", ["Review top cities; concentrate the next push where you already index."]),
        ],
        "kpi": "Monthly listeners and top-city concentration",
    },
    "shortform_posts_per_week": {
        "title": "Cadence fix",
        "why": "You are not publishing often enough to learn what works.",
        "weeks": [
            ("Week 1", ["Batch-shoot one day; plan the edit before the shoot."]),
            ("Week 2", ["Hit the peer median cadence before changing the creative."]),
            ("Week 3", ["Fixed posting days; consistency beats production value."]),
            ("Week 4", ["Keep the format that beat your median; drop the rest."]),
        ],
        "kpi": "Posts per week sustained",
    },
}

DEFAULT_PLAN = {
    "title": "Consolidate and compound",
    "why": "No dimension is decisively behind the peer median, so the job is to widen the lead.",
    "weeks": [
        ("Week 1", ["Identify your single strongest dimension and double the resource behind it."]),
        ("Week 2", ["Re-tier your peer set upward — you may be benchmarking too low."]),
        ("Week 3", ["Convert reach into owned contacts: WhatsApp list and email."]),
        ("Week 4", ["Book one cross-border touchpoint to open a new market."]),
    ],
    "kpi": "Widening lead on your strongest dimension",
}


def plans(artist: dict, peers: list, radar: list | None = None) -> dict:
    """Build a prioritised 30-day campaign plan from the biggest gaps."""
    s = swot(artist, peers, radar)
    chosen, seen = [], set()
    for w in s["weaknesses"]:
        key = w.get("key")
        if key in PLAYBOOKS and key not in seen:
            pb = PLAYBOOKS[key]
            chosen.append({
                "key": key,
                "title": pb["title"],
                "why": pb["why"],
                "trigger": w["text"],
                "weeks": [{"label": lbl, "tasks": tasks} for lbl, tasks in pb["weeks"]],
                "kpi": pb["kpi"],
                "priority": len(chosen) + 1,
                "gap_pct": round(abs(w["pct"])) if w.get("pct") else None,
            })
            seen.add(key)
        if len(chosen) >= 3:
            break

    if not chosen:
        chosen.append({
            "key": "consolidate", "title": DEFAULT_PLAN["title"], "why": DEFAULT_PLAN["why"],
            "trigger": "No dimension more than 20% below the peer median.",
            "weeks": [{"label": l, "tasks": t} for l, t in DEFAULT_PLAN["weeks"]],
            "kpi": DEFAULT_PLAN["kpi"], "priority": 1, "gap_pct": None,
        })

    return {"plans": chosen, "peer_count": len(peers),
            "based_on": [w["text"] for w in s["weaknesses"][:3]]}
