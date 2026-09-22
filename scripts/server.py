#!/usr/bin/env python3
"""Chartmeter web app — marketing homepage, artist accounts, dashboard.

    python3 scripts/server.py --port 3000

Stdlib only. Routes:
  /                 marketing homepage (signed out) / dashboard (signed in)
  /api/auth/*       signup, login, logout, session
  /api/links        parse pasted platform URLs
  /api/sync         fetch stats from the linked platforms
  /api/discover     suggest competitors from your own stats
  /api/*            workspace data (per-account)

Each account owns an isolated workspace in data/accounts.json (gitignored).
A signed-out visitor sees a read-only demo workspace seeded from data/*.yml,
so the product can be shown without an account.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import http.cookies
import json
import mimetypes
import os
import re
import statistics
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import accounts  # noqa: E402
import chartmeter as cm  # noqa: E402
import discover  # noqa: E402
import insights  # noqa: E402
import links as linkmod  # noqa: E402
import providers  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBAPP = os.path.join(ROOT, "webapp")
DEMO_PATH = os.path.join(ROOT, "data", "workspace.json")

_lock = threading.Lock()
COOKIE = "cm_session"


# --------------------------------------------------------------------------- demo ws

def seed_workspace() -> dict:
    return {
        "artist": cm.load("artist-baseline.yml"),
        "competitors": cm.load("competitors.yml").get("competitors") or [],
        "radar": cm.load("radar.yml").get("contacts") or [],
        "swipe": cm.load("swipe-file.yml").get("entries") or [],
    }


def load_demo() -> dict:
    if os.path.exists(DEMO_PATH):
        try:
            with open(DEMO_PATH, encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            pass
    ws = seed_workspace()
    save_demo(ws)
    return ws


def save_demo(ws: dict) -> None:
    os.makedirs(os.path.dirname(DEMO_PATH), exist_ok=True)
    tmp = DEMO_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(ws, fh, indent=2)
    os.replace(tmp, DEMO_PATH)


# --------------------------------------------------------------------------- analysis

def compute_gaps(ws: dict) -> dict:
    artist = ws.get("artist") or {}
    peers = cm.peers(artist, ws.get("competitors") or [])
    am = artist.get("metrics") or {}
    rows = []
    for key, label in cm.METRICS:
        vals = [v for v in ((c.get("metrics") or {}).get(key) for c in peers)
                if isinstance(v, (int, float))]
        ours = am.get(key)
        if not vals or not isinstance(ours, (int, float)):
            rows.append({"key": key, "label": label, "ours": ours, "median": None,
                         "pct": None, "read": "no data", "action": None})
            continue
        med = statistics.median(vals)
        delta = ours - med
        rows.append({
            "key": key, "label": label, "ours": ours, "median": med,
            "pct": (delta / med * 100) if med else None,
            "read": "surplus" if delta > 0 else ("parity" if delta == 0 else "deficit"),
            "action": cm.ACTIONS.get(key) if delta < 0 else None,
            "best": max(vals),
        })
    deficits = sorted([r for r in rows if r["read"] == "deficit" and r["pct"] is not None],
                      key=lambda r: r["pct"])
    surpluses = sorted([r for r in rows if r["read"] == "surplus" and r["pct"] is not None],
                       key=lambda r: -r["pct"])
    scored = [r for r in rows if r["pct"] is not None]
    health = round(sum(1 for r in scored if r["read"] != "deficit") / len(scored) * 100) if scored else 0
    return {"artist": artist.get("name"), "tier": artist.get("tier"),
            "subgenre": artist.get("subgenre"),
            "peers": [c.get("name") for c in peers], "peer_count": len(peers),
            "rows": rows, "deficits": deficits, "surpluses": surpluses,
            "health": health, "manual_only": providers.MANUAL_ONLY}


def compute_overview(ws: dict) -> dict:
    artist = ws.get("artist") or {}
    gaps = compute_gaps(ws)
    radar = ws.get("radar") or []
    cold = [c.get("name") for c in radar if (cm.days_since(c.get("last_contact")) or 0) > 30]
    linked = artist.get("links") or {}
    peers_list = cm.peers(artist, ws.get("competitors") or [])
    return {
        "artist": artist,
        "cpp": insights.cpp(artist, peers_list),
        "counts": {"competitors": len(ws.get("competitors") or []),
                   "peers": gaps["peer_count"], "radar": len(radar),
                   "swipe": len(ws.get("swipe") or []), "cold": len(cold),
                   "links": len(linked)},
        "health": gaps["health"],
        "top_deficits": gaps["deficits"][:3],
        "top_surpluses": gaps["surpluses"][:2],
        "cold_contacts": cold,
        "linked": linked,
        "last_sync": artist.get("last_sync"),
    }


# --------------------------------------------------------------------------- validation

ALLOWED_TIERS = set(cm.TIERS)
METRIC_KEYS = {k for k, _ in cm.METRICS}


def coerce_metrics(raw: dict):
    out, errors = {}, []
    for key, val in (raw or {}).items():
        if key not in METRIC_KEYS or val in (None, ""):
            continue
        try:
            out[key] = float(val) if key == "crossborder_listener_share" else int(float(val))
        except (TypeError, ValueError):
            errors.append("%s must be a number." % key)
    return out, errors


def clean_competitor(payload: dict):
    errors = []
    name = str(payload.get("name") or "").strip()
    if not name:
        errors.append("Name is required.")
    metrics, merr = coerce_metrics(payload.get("metrics"))
    errors += merr
    ml = metrics.get("monthly_listeners")
    tier = str(payload.get("tier") or "").strip()
    if tier not in ALLOWED_TIERS:
        tier = cm.tier_for(ml or 0)
    elif ml is not None and cm.tier_for(ml) != tier:
        errors.append("Tier '%s' disagrees with %s monthly listeners (expected '%s')."
                      % (tier, format(int(ml), ","), cm.tier_for(ml)))
    return {
        "name": name,
        "country": str(payload.get("country") or "UG").strip(),
        "city": str(payload.get("city") or "").strip(),
        "subgenre": str(payload.get("subgenre") or "").strip(),
        "tier": tier,
        "active_last_120d": bool(payload.get("active_last_120d", True)),
        "last_audit": str(payload.get("last_audit") or _dt.date.today().isoformat()),
        "arena_channel": str(payload.get("arena_channel") or "").strip(),
        "visual_hooks": str(payload.get("visual_hooks") or "").strip(),
        "performance_loop": str(payload.get("performance_loop") or "").strip(),
        "dropoff": str(payload.get("dropoff") or "").strip(),
        "metrics": metrics,
        "links": payload.get("links") or {},
    }, errors


# --------------------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    server_version = "Chartmeter"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *a):
        sys.stderr.write("  %s\n" % (fmt % a))

    # ---- plumbing
    def _send(self, code, body=b"", ctype="application/json", cookie=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def json(self, obj, code=200, cookie=None):
        self._send(code, json.dumps(obj).encode(), "application/json; charset=utf-8", cookie)

    def body(self) -> dict:
        try:
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return {}

    def session_token(self):
        raw = self.headers.get("Cookie")
        if not raw:
            return None
        try:
            c = http.cookies.SimpleCookie(raw)
        except http.cookies.CookieError:
            return None
        return c[COOKIE].value if COOKIE in c else None

    def current_user(self):
        return accounts.user_for_session(self.session_token())

    def workspace(self):
        """-> (workspace, email_or_None). Signed-out users get the demo copy."""
        user = self.current_user()
        if user:
            return user["workspace"], user["email"]
        return load_demo(), None

    def persist(self, ws, email):
        if email:
            accounts.save_workspace(email, ws)
        else:
            save_demo(ws)

    # ---- routing
    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith("/api/"):
            return self.api_get(path)
        return self.static(path)

    do_HEAD = do_GET

    def do_POST(self):
        path = urlparse(self.path).path
        payload = self.body()

        # ---------- auth
        if path == "/api/auth/signup":
            user, errors = accounts.create_user(
                payload.get("email"), payload.get("password"),
                payload.get("artist_name"),
                {"city": payload.get("city"), "country": payload.get("country"),
                 "subgenre": payload.get("subgenre")})
            if errors:
                return self.json({"errors": errors}, 400)
            token = accounts.start_session(user["email"])
            return self.json({"ok": True, "user": self.pub(user)}, 201, self.cookie(token))

        if path == "/api/auth/login":
            user = accounts.authenticate(payload.get("email"), payload.get("password"))
            if not user:
                return self.json({"errors": ["Incorrect email or password."]}, 401)
            token = accounts.start_session(user["email"])
            return self.json({"ok": True, "user": self.pub(user)}, 200, self.cookie(token))

        if path == "/api/auth/logout":
            accounts.end_session(self.session_token())
            return self.json({"ok": True}, 200, self.cookie("", expire=True))

        # ---------- links & sync
        if path == "/api/links":
            parsed = linkmod.parse_many(payload.get("urls") or payload.get("text") or [])
            with _lock:
                ws, email = self.workspace()
                artist = ws.setdefault("artist", {})
                stored = artist.setdefault("links", {})
                stored.update(parsed["links"])
                self.persist(ws, email)
            return self.json({"ok": True, "links": stored, "unknown": parsed["unknown"],
                              "added": list(parsed["links"])})

        if path == "/api/links/remove":
            key = str(payload.get("platform") or "")
            with _lock:
                ws, email = self.workspace()
                (ws.get("artist") or {}).get("links", {}).pop(key, None)
                self.persist(ws, email)
            return self.json({"ok": True})

        if path == "/api/sync":
            with _lock:
                ws, email = self.workspace()
                artist = ws.setdefault("artist", {})
                stored = artist.get("links") or {}
            if not stored:
                return self.json({"errors": ["Add at least one platform link first."]}, 400)
            result = linkmod.sync(stored)
            with _lock:
                ws, email = self.workspace()
                artist = ws.setdefault("artist", {})
                artist.setdefault("metrics", {}).update(result["metrics"])
                artist["last_sync"] = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
                ml = artist["metrics"].get("monthly_listeners")
                if isinstance(ml, (int, float)):
                    artist["tier"] = cm.tier_for(ml)
                self.persist(ws, email)
            return self.json({"ok": True, "results": result["results"],
                              "metrics": result["metrics"],
                              "needs_setup": result["needs_setup"],
                              "manual_only": providers.MANUAL_ONLY,
                              "last_sync": artist.get("last_sync")})

        # ---------- workspace
        if path == "/api/artist":
            with _lock:
                ws, email = self.workspace()
                artist = ws.setdefault("artist", {})
                for f in ("name", "city", "country", "subgenre"):
                    if payload.get(f) is not None:
                        artist[f] = str(payload[f]).strip()
                metrics, errors = coerce_metrics(payload.get("metrics"))
                if errors:
                    return self.json({"errors": errors}, 400)
                artist.setdefault("metrics", {}).update(metrics)
                ml = artist["metrics"].get("monthly_listeners")
                if isinstance(ml, (int, float)):
                    artist["tier"] = cm.tier_for(ml)
                artist["last_audit"] = _dt.date.today().isoformat()
                self.persist(ws, email)
            return self.json({"ok": True, "artist": artist})

        if path == "/api/competitors":
            entry, errors = clean_competitor(payload)
            if errors:
                return self.json({"errors": errors}, 400)
            with _lock:
                ws, email = self.workspace()
                comps = ws.setdefault("competitors", [])
                if any(c.get("name") == entry["name"] for c in comps):
                    return self.json({"errors": ["'%s' is already tracked." % entry["name"]]}, 400)
                comps.append(entry)
                self.persist(ws, email)
            return self.json({"ok": True, "competitor": entry}, 201)

        if path == "/api/discover/accept":
            names = payload.get("names") or []
            added = []
            with _lock:
                ws, email = self.workspace()
                comps = ws.setdefault("competitors", [])
                have = {c.get("name") for c in comps}
                pool = {c.get("name"): c for c in discover.load_pool()}
                for n in names:
                    cand = pool.get(n)
                    if not cand or n in have:
                        continue
                    entry, _ = clean_competitor({
                        "name": cand.get("name"), "country": cand.get("country"),
                        "city": cand.get("city"), "subgenre": cand.get("subgenre"),
                        "metrics": cand.get("metrics"), "links": cand.get("links"),
                        "active_last_120d": cand.get("active_last_120d", True),
                    })
                    comps.append(entry)
                    added.append(entry["name"])
                self.persist(ws, email)
            return self.json({"ok": True, "added": added})

        if path == "/api/reset":
            user = self.current_user()
            if user:
                ws = user["workspace"]
                ws["competitors"] = []
                accounts.save_workspace(user["email"], ws)
            else:
                save_demo(seed_workspace())
            return self.json({"ok": True})

        return self.json({"error": "not found"}, 404)

    def do_DELETE(self):
        path = urlparse(self.path).path
        m = re.match(r"^/api/competitors/(.+)$", path)
        if not m:
            return self.json({"error": "not found"}, 404)
        name = unquote(m.group(1))
        with _lock:
            ws, email = self.workspace()
            comps = ws.setdefault("competitors", [])
            before = len(comps)
            ws["competitors"] = [c for c in comps if c.get("name") != name]
            if len(ws["competitors"]) == before:
                return self.json({"error": "no such competitor"}, 404)
            self.persist(ws, email)
        return self.json({"ok": True})

    # ---- helpers
    def cookie(self, token, expire=False):
        bits = ["%s=%s" % (COOKIE, token), "Path=/", "HttpOnly", "SameSite=Lax"]
        bits.append("Max-Age=0" if expire else "Max-Age=%d" % (accounts.SESSION_DAYS * 86400))
        return "; ".join(bits)

    @staticmethod
    def pub(user):
        return {"email": user["email"], "artist_name": (user["workspace"]["artist"] or {}).get("name")}

    def api_get(self, path):
        if path == "/api/auth/session":
            user = self.current_user()
            return self.json({"signed_in": bool(user),
                              "user": self.pub(user) if user else None})

        with _lock:
            ws, email = self.workspace()
        demo = email is None

        if path == "/api/overview":
            d = compute_overview(ws)
            d["demo"] = demo
            return self.json(d)
        if path == "/api/gaps":
            d = compute_gaps(ws)
            d["demo"] = demo
            return self.json(d)
        if path == "/api/competitors":
            return self.json({"competitors": ws.get("competitors") or [],
                              "artist": ws.get("artist") or {},
                              "tier_labels": cm.TIER_LABEL, "demo": demo,
                              "metrics": [{"key": k, "label": l} for k, l in cm.METRICS]})
        if path == "/api/swot":
            artist = ws.get("artist") or {}
            prs = cm.peers(artist, ws.get("competitors") or [])
            d = insights.swot(artist, prs, ws.get("radar") or [])
            d["demo"] = demo
            return self.json(d)
        if path == "/api/plans":
            artist = ws.get("artist") or {}
            prs = cm.peers(artist, ws.get("competitors") or [])
            d = insights.plans(artist, prs, ws.get("radar") or [])
            d["demo"] = demo
            return self.json(d)
        if path == "/api/cpp":
            artist = ws.get("artist") or {}
            prs = cm.peers(artist, ws.get("competitors") or [])
            return self.json(insights.cpp(artist, prs))
        if path == "/api/compare":
            artist = ws.get("artist") or {}
            prs = cm.peers(artist, ws.get("competitors") or [])
            rows = []
            for key, label in cm.METRICS:
                ours = (artist.get("metrics") or {}).get(key)
                acts = []
                for p in prs:
                    v = (p.get("metrics") or {}).get(key)
                    if isinstance(v, (int, float)):
                        acts.append({"name": p.get("name"), "value": v})
                rows.append({"key": key, "label": label, "ours": ours,
                             "acts": sorted(acts, key=lambda x: -x["value"])})
            return self.json({"rows": rows, "artist": artist.get("name"),
                              "peers": [p.get("name") for p in prs], "demo": demo})
        if path == "/api/discover":
            return self.json(discover.suggest(ws.get("artist") or {},
                                              ws.get("competitors") or []))
        if path == "/api/links":
            return self.json({"links": (ws.get("artist") or {}).get("links") or {},
                              "syncable": linkmod.SYNCABLE,
                              "last_sync": (ws.get("artist") or {}).get("last_sync")})
        if path == "/api/radar":
            rows = []
            for c in ws.get("radar") or []:
                d = dict(c)
                d["days"] = cm.days_since(c.get("last_contact"))
                rows.append(d)
            return self.json({"contacts": rows, "demo": demo})
        if path == "/api/swipe":
            return self.json({"entries": ws.get("swipe") or [], "demo": demo})
        if path == "/api/providers":
            out = []
            for name in providers.REGISTRY:
                p = providers.get(name)
                out.append({"name": name, "ready": p.available(), "missing": p.missing(),
                            "metrics": list(p.METRICS), "note": p.NOTE})
            return self.json({"providers": out, "manual_only": providers.MANUAL_ONLY})
        return self.json({"error": "not found"}, 404)

    def static(self, path):
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        full = os.path.normpath(os.path.join(WEBAPP, rel))
        if not full.startswith(WEBAPP) or not os.path.isfile(full):
            full = os.path.join(WEBAPP, "index.html")
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
    ap.add_argument("--reset", action="store_true", help="re-seed the signed-out demo workspace")
    args = ap.parse_args()

    if args.reset and os.path.exists(DEMO_PATH):
        os.remove(DEMO_PATH)
    load_demo()

    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print("Chartmeter on http://%s:%d" % (args.host, args.port))
    print("Accounts: data/accounts.json  ·  Demo workspace: data/workspace.json (both gitignored)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
