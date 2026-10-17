"""Single-user password login with a signed, expiring session cookie."""

import hashlib
import hmac
import os
import time

COOKIE = "tl_session"
SESSION_SECONDS = 12 * 3600


def configured() -> bool:
    return bool(os.environ.get("APP_PASSWORD")) and len(os.environ.get("SESSION_SECRET", "")) >= 32


def _sign(payload: str) -> str:
    return hmac.new(os.environ["SESSION_SECRET"].encode(), payload.encode(), hashlib.sha256).hexdigest()


def password_ok(candidate: str) -> bool:
    expected = os.environ.get("APP_PASSWORD", "")
    return bool(expected) and hmac.compare_digest(candidate.encode(), expected.encode())


def make_session(now: float | None = None) -> str:
    expiry = int((now or time.time()) + SESSION_SECONDS)
    return f"{expiry}.{_sign(str(expiry))}"


def session_ok(cookie: str | None, now: float | None = None) -> bool:
    if not cookie or "." not in cookie or not configured():
        return False
    expiry, sig = cookie.split(".", 1)
    if not expiry.isdigit() or not hmac.compare_digest(sig, _sign(expiry)):
        return False
    return int(expiry) > (now or time.time())


def cron_ok(authorization: str | None) -> bool:
    """Vercel Cron sends `Authorization: Bearer <CRON_SECRET>`."""
    secret = os.environ.get("CRON_SECRET", "")
    return bool(secret) and bool(authorization) and hmac.compare_digest(authorization.encode(), f"Bearer {secret}".encode())
