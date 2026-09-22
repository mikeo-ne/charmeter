#!/usr/bin/env python3
"""User accounts, sessions and per-artist workspaces for Chartmeter.

Stdlib only. Users live in data/accounts.json (gitignored), each with their own
workspace so two artists never see each other's numbers.

Password handling: PBKDF2-HMAC-SHA256, 240k iterations, 16-byte random salt,
constant-time comparison. Sessions are 32-byte urlsafe tokens with an expiry.

This is demo-grade auth: good hashing, but a JSON file store and in-process
sessions. Before real customer data, move to a database and serve over TLS.
"""

from __future__ import annotations

import base64
import datetime as _dt
import hashlib
import hmac
import json
import os
import re
import secrets
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(ROOT, "data", "accounts.json")

ITERATIONS = 240_000
SESSION_DAYS = 30
_lock = threading.RLock()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# --------------------------------------------------------------------------- store

def _blank() -> dict:
    return {"users": {}, "sessions": {}}


def _read() -> dict:
    if not os.path.exists(STORE):
        return _blank()
    try:
        with open(STORE, encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return _blank()
    data.setdefault("users", {})
    data.setdefault("sessions", {})
    return data


def _write(data: dict) -> None:
    os.makedirs(os.path.dirname(STORE), exist_ok=True)
    tmp = STORE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, STORE)


# --------------------------------------------------------------------------- crypto

def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return "pbkdf2_sha256$%d$%s$%s" % (
        ITERATIONS,
        base64.b64encode(salt).decode(),
        base64.b64encode(dk).decode(),
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_b64, hash_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), base64.b64decode(salt_b64), int(iters)
        )
        return hmac.compare_digest(dk, base64.b64decode(hash_b64))
    except (ValueError, TypeError):
        return False


# --------------------------------------------------------------------------- validation

def validate_signup(email: str, password: str, artist_name: str) -> list:
    errors = []
    if not EMAIL_RE.match(email or ""):
        errors.append("Enter a valid email address.")
    if len(password or "") < 8:
        errors.append("Password must be at least 8 characters.")
    if not (artist_name or "").strip():
        errors.append("Artist name is required.")
    return errors


# --------------------------------------------------------------------------- users

def create_user(email: str, password: str, artist_name: str, profile: dict | None = None):
    """Return (user_dict, errors)."""
    email = (email or "").strip().lower()
    artist_name = (artist_name or "").strip()
    errors = validate_signup(email, password, artist_name)
    if errors:
        return None, errors

    with _lock:
        data = _read()
        if email in data["users"]:
            return None, ["An account with that email already exists."]

        profile = profile or {}
        user = {
            "email": email,
            "password": hash_password(password),
            "created": _dt.date.today().isoformat(),
            "workspace": {
                "artist": {
                    "name": artist_name,
                    "city": (profile.get("city") or "").strip(),
                    "country": (profile.get("country") or "UG").strip(),
                    "subgenre": (profile.get("subgenre") or "").strip(),
                    "tier": "upcoming",
                    "last_audit": _dt.date.today().isoformat(),
                    "metrics": {},
                    "links": {},
                    "milestones": [],
                },
                "competitors": [],
                "radar": [],
                "swipe": [],
            },
        }
        data["users"][email] = user
        _write(data)
    return user, []


def authenticate(email: str, password: str):
    email = (email or "").strip().lower()
    with _lock:
        data = _read()
        user = data["users"].get(email)
    if not user or not verify_password(password or "", user["password"]):
        return None
    return user


def start_session(email: str) -> str:
    token = secrets.token_urlsafe(32)
    expires = (_dt.datetime.now() + _dt.timedelta(days=SESSION_DAYS)).isoformat()
    with _lock:
        data = _read()
        data["sessions"][token] = {"email": email, "expires": expires}
        _write(data)
    return token


def end_session(token: str) -> None:
    if not token:
        return
    with _lock:
        data = _read()
        if data["sessions"].pop(token, None) is not None:
            _write(data)


def user_for_session(token: str):
    if not token:
        return None
    with _lock:
        data = _read()
        sess = data["sessions"].get(token)
        if not sess:
            return None
        try:
            if _dt.datetime.fromisoformat(sess["expires"]) < _dt.datetime.now():
                data["sessions"].pop(token, None)
                _write(data)
                return None
        except (ValueError, KeyError):
            return None
        return data["users"].get(sess["email"])


def save_workspace(email: str, workspace: dict) -> None:
    with _lock:
        data = _read()
        if email in data["users"]:
            data["users"][email]["workspace"] = workspace
            _write(data)


def get_workspace(email: str):
    with _lock:
        data = _read()
        user = data["users"].get(email)
        return user["workspace"] if user else None
