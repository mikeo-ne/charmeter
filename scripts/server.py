#!/usr/bin/env python3
"""Chartmeter web app — client-facing demo server.

A dependency-free HTTP server (stdlib only) exposing the Chartmeter analysis
engine as a JSON API plus a single-page front end in webapp/.

    python3 scripts/server.py --port 3000

Design notes for demos:
  * The YAML files in data/ are the SEED. On first run they are loaded into a
    working copy at data/workspace.json (gitignored). All edits from the UI go
    to the working copy, so a client can add and delete competitors freely
    without ever dirtying the repo.
  * "Reset demo" re-seeds from the YAML.
  * Analysis (tiering, peer matching, gap medians) is imported from
    chartmeter.py, so the site and the CLI can never disagree.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import statistics
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import chartmeter as cm  # noqa: E402
import providers  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBAPP = os.path.join(ROOT, "webapp")
STATE_PATH = os.path.join(ROOT, "data", "workspace.json")

_lock = threading.Lock()


# --------------------------------------------------------------------------- state

def seed_state() -> dict:
    """Build a fresh working copy from the YAML seed files."""
    artist = cm.load("artist-baseline.yml")
    competitors = cm.load("competitors.yml").get("competitors") or []
    radar = cm.load("radar.yml").get("contacts") or []
    swipe = cm.load("swipe-file.yml").get("entries") or []
    return {
        "artist": artist,
        "competitors": competitors,
        "radar": radar,
        "swipe": swipe,
    }


def load_state() -> dict:
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            pass
    state = seed_state()
    save_state(state)
    return state


def save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)
    os.replace(tmp, STATE_PATH)


# --------------------------------------------------------------------------- analysis

def compute_gaps(state: dict) -> dict:
    artist = state["artist"]
    competitors = state["competitors"]
    peers = cm.peers(artist, competitors)
    am = artist.get("metrics") or {}

    rows = []
    for key, label in cm.METRICS:
        vals = [
            (c.get("metrics") or {}).get(key)
            for c in peers
        ]
        vals = [v for v in vals if isinstance(v, (int, float))]
        ours = am.get(key)
        if not vals or not isinstance(ours, (int, float)):
            rows.append({
                "key": key, "label": label, "ours": ours, "median": None,
                "pct": None, "read": "no data", "action": None,
            })
            continue
        med = statistics.median(vals)
        delta = ours - med
        pct = (delta / med * 100) if med else None
        read = "surplus" if delta > 0 else ("parity" if delta == 0 else "deficit")
        rows.append({
            "key": key, "label": label, "ours": ours, "median": med,
            "pct": pct, "read": read,
            "action": cm.ACTIONS.get(key) if delta < 0 else None,
            "best": max(vals),
        })

    deficits = sorted(
        [r for r in rows if r["read"] == "deficit" and r["pct"] is not None],
        key=lambda r: r["pct"],
    )
    surpluses = sorted(
        [r for r in rows if r["read"] == "surplus" and r["pct"] is not None],
        key=lambda r: -r["pct"],
    )
    scored = [r for r in rows if r["pct"] is not None]
    health = round(sum(1 for r in scored if r["read"] != "deficit") / len(scored) * 100) if scored else 0

    return {
        "artist": artist.get("name"),
        "tier": artist.get("tier"),
        "subgenre": artist.get("subgenre"),
        "peers": [c.get("name") for c in peers],
        "peer_count": len(peers),
        "rows": rows,
        "deficits": deficits,
        "surpluses": surpluses,
        "health": health,
        "manual_only": providers.MANUAL_ONLY,
    }


def compute_overview(state: dict) -> dict:
    artist = state["artist"]
    competitors = state["competitors"]
    gaps = compute_gaps(state)
    tiers = {}
    for c in competitors:
        tiers.setdefault(c.get("tier", "unknown"), []).append(c.get("name"))
    radar = state["radar"]
    cold = [
        c.get("name") for c in radar
        if (cm.days_since(c.get("last_contact")) or 0) > 30
    ]
    return {
        "artist": artist,
        "counts": {
            "competitors": len(competitors),
            "peers": gaps["peer_count"],
            "radar": len(radar),
            "swipe": len(state["swipe"]),
            "cold": len(cold),
        },
        "tiers": tiers,
        "health": gaps["health"],
        "top_deficits": gaps["deficits"][:3],
        "top_surpluses": gaps["surpluses"][:2],
        "cold_contacts": cold,
        "tier_labels": cm.TIER_LABEL,
    }


def provider_status() -> list:
    out = []
    for name in providers.REGISTRY:
        p = providers.get(name)
        out.append({
            "name": name,
            "ready": p.available(),
            "missing": p.missing(),
            "metrics": list(p.METRICS),
            "note": p.NOTE,
        })
    return out


# --------------------------------------------------------------------------- validation

ALLOWED_TIERS = set(cm.TIERS)
METRIC_KEYS = {k for k, _ in cm.METRICS}


def clean_competitor(payload: dict) -> tuple[dict, list]:
    errors = []
    name = str(payload.get("name") or "").strip()
    if not name:
        errors.append("Name is required.")

    metrics = {}
    for key in METRIC_KEYS:
        raw = (payload.get("metrics") or {}).get(key)
        if raw in (None, ""):
            continue
        try:
            metrics[key] = float(raw) if key == "crossborder_listener_share" else int(float(raw))
        except (TypeError, ValueError):
            errors.append("%s must be a number." % key)

    ml = metrics.get("monthly_listeners")
    tier = str(payload.get("tier") or "").strip()
    if tier not in ALLOWED_TIERS:
        tier = cm.tier_for(ml or 0)
    elif ml is not None and cm.tier_for(ml) != tier:
        # Enforce the Phase 2 rule rather than silently storing a bad tier.
        errors.append(
            "Tier '%s' disagrees with %s monthly listeners (expected '%s')."
            % (tier, format(int(ml), ","), cm.tier_for(ml))
        )

    entry = {
        "name": name,
        "country": str(payload.get("country") or "").strip() or "UG",
        "city": str(payload.get("city") or "").strip(),
        "subgenre": str(payload.get("subgenre") or "").strip(),
        "tier": tier,
        "active_last_120d": bool(payload.get("active_last_120d", True)),
        "last_audit": str(payload.get("last_audit") or "").strip(),
        "arena_channel": str(payload.get("arena_channel") or "").strip(),
        "visual_hooks": str(payload.get("visual_hooks") or "").strip(),
        "performance_loop": str(payload.get("performance_loop") or "").strip(),
        "dropoff": str(payload.get("dropoff") or "").strip(),
        "metrics": metrics,
    }
    return entry, errors


# --------------------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    server_version = "Chartmeter"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *a):  # quieter console during a demo
        sys.stderr.write("  %s\n" % (fmt % a))

    # ---- helpers
    def _send(self, code, body=b"", ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def json(self, obj, code=200):
        self._send(code, json.dumps(obj).encode(), "application/json; charset=utf-8")

    def body(self) -> dict:
        try:
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return {}

    # ---- routing
    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith("/api/"):
            return self.api_get(path)
        return self.static(path)

    do_HEAD = do_GET

    def do_POST(self):
        path = urlparse(self.path).path
        with _lock:
            state = load_state()

            if path == "/api/competitors":
                entry, errors = clean_competitor(self.body())
                if errors:
                    return self.json({"errors": errors}, 400)
                if any(c.get("name") == entry["name"] for c in state["competitors"]):
                    return self.json({"errors": ["'%s' already exists." % entry["name"]]}, 400)
                state["competitors"].append(entry)
                save_state(state)
                return self.json({"ok": True, "competitor": entry}, 201)

            if path == "/api/artist":
                payload = self.body()
                artist = state["artist"]
                for field in ("name", "city", "country", "subgenre", "tier"):
                    if payload.get(field):
                        artist[field] = str(payload[field]).strip()
                metrics = artist.setdefault("metrics", {})
                for key in METRIC_KEYS:
                    raw = (payload.get("metrics") or {}).get(key)
                    if raw in (None, ""):
                        continue
                    try:
                        metrics[key] = float(raw) if key == "crossborder_listener_share" else int(float(raw))
                    except (TypeError, ValueError):
                        return self.json({"errors": ["%s must be a number." % key]}, 400)
                ml = metrics.get("monthly_listeners")
                if ml is not None:
                    artist["tier"] = cm.tier_for(ml)
                save_state(state)
                return self.json({"ok": True, "artist": artist})

            if path == "/api/reset":
                state = seed_state()
                save_state(state)
                return self.json({"ok": True})

        return self.json({"error": "not found"}, 404)

    def do_DELETE(self):
        path = urlparse(self.path).path
        m = re.match(r"^/api/competitors/(.+)$", path)
        if not m:
            return self.json({"error": "not found"}, 404)
        from urllib.parse import unquote
        name = unquote(m.group(1))
        with _lock:
            state = load_state()
            before = len(state["competitors"])
            state["competitors"] = [c for c in state["competitors"] if c.get("name") != name]
            if len(state["competitors"]) == before:
                return self.json({"error": "no such competitor"}, 404)
            save_state(state)
        return self.json({"ok": True})

    def api_get(self, path):
        with _lock:
            state = load_state()
        if path == "/api/overview":
            return self.json(compute_overview(state))
        if path == "/api/gaps":
            return self.json(compute_gaps(state))
        if path == "/api/competitors":
            return self.json({
                "competitors": state["competitors"],
                "artist": state["artist"],
                "tier_labels": cm.TIER_LABEL,
                "metrics": [{"key": k, "label": l} for k, l in cm.METRICS],
            })
        if path == "/api/radar":
            rows = []
            for c in state["radar"]:
                d = dict(c)
                d["days"] = cm.days_since(c.get("last_contact"))
                rows.append(d)
            return self.json({"contacts": rows})
        if path == "/api/swipe":
            return self.json({"entries": state["swipe"]})
        if path == "/api/providers":
            return self.json({
                "providers": provider_status(),
                "manual_only": providers.MANUAL_ONLY,
            })
        return self.json({"error": "not found"}, 404)

    def static(self, path):
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        full = os.path.normpath(os.path.join(WEBAPP, rel))
        if not full.startswith(WEBAPP) or not os.path.isfile(full):
            full = os.path.join(WEBAPP, "index.html")  # SPA fallback
            if not os.path.isfile(full):
                return self._send(404, b"not found", "text/plain")
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        with open(full, "rb") as fh:
            data = fh.read()
        self._send(200, data, ctype)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=3000)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--reset", action="store_true", help="re-seed the working copy on start")
    args = ap.parse_args()

    if args.reset and os.path.exists(STATE_PATH):
        os.remove(STATE_PATH)
    load_state()

    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print("Chartmeter demo running on http://%s:%d" % (args.host, args.port))
    print("Working copy: %s (edits never touch data/*.yml)" % os.path.relpath(STATE_PATH, ROOT))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
