"""A small read-only Groww client for the web app and the daily snapshot job.

It talks to the same REST endpoints as the official SDK (growwapi 1.5.0) but
only implements GET requests for reading data, plus the login call. There is
no code path here that could create, modify or cancel an order, and a test
checks that no order-writing endpoint appears in this file.

It avoids the SDK because the SDK downloads a 20 MB instrument file on every
start and pins pandas < 3.
"""

import base64
import hashlib
import hmac
import os
import struct
import time
import uuid
from typing import Any

import requests

from .readonly import redact

BASE_URL = "https://api.groww.in/v1"
TOKEN_URL = "https://api.groww.in/v1/token/api/access"
INSTRUMENT_CSV_URL = "https://growwapi-assets.groww.in/instruments/instrument.csv"


class GrowwReadError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def totp_now(secret_b32: str, at: float | None = None, step: int = 30, digits: int = 6) -> str:
    """RFC 6238 TOTP (SHA-1), the same scheme pyotp uses by default."""
    key = base64.b32decode(secret_b32.replace(" ", "").upper() + "=" * (-len(secret_b32.replace(" ", "")) % 8))
    counter = int((time.time() if at is None else at) // step)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code).zfill(digits)


def _headers(token: str) -> dict:
    return {
        "x-request-id": str(uuid.uuid4()),
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
        "x-client-id": "growwapi",
        "x-client-platform": "growwapi-python-client",
        "x-client-platform-version": "1.5.0",
        "x-api-version": "1.0",
    }


def _parse(resp: requests.Response) -> Any:
    try:
        body = resp.json()
    except ValueError:
        raise GrowwReadError(f"Groww returned a non-JSON response (HTTP {resp.status_code})", resp.status_code) from None
    if isinstance(body, dict) and body.get("status") == "FAILURE":
        err = body.get("error") or {}
        raise GrowwReadError(redact(f"Groww error {err.get('code')}: {err.get('message')}"), resp.status_code)
    if not resp.ok:
        raise GrowwReadError(f"Groww request failed (HTTP {resp.status_code})", resp.status_code)
    return body.get("payload", body) if isinstance(body, dict) else body


def first_list(payload: Any) -> list:
    """Groww wraps lists in a payload object (e.g. {"order_list": [...]}); return the first list found."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for v in payload.values():
            if isinstance(v, list):
                return v
    return []


class GrowwReadClient:
    def __init__(self, token: str, session: requests.Session | None = None, timeout: float = 15.0):
        self._token = token
        self._http = session or requests.Session()
        self._timeout = timeout

    def __repr__(self) -> str:
        return "GrowwReadClient(<token hidden>)"

    @classmethod
    def from_env(cls, session: requests.Session | None = None) -> "GrowwReadClient":
        api_key = os.environ.get("GROWW_API_KEY", "")
        totp_secret = os.environ.get("GROWW_TOTP_SECRET", "")
        api_secret = os.environ.get("GROWW_API_SECRET", "")
        if not api_key or not (totp_secret or api_secret):
            raise GrowwReadError("GROWW_API_KEY and GROWW_TOTP_SECRET (or GROWW_API_SECRET) are not set")
        if totp_secret:
            body = {"key_type": "totp", "totp": totp_now(totp_secret)}
        else:
            ts = int(time.time())
            body = {"key_type": "approval", "timestamp": ts,
                    "checksum": hashlib.sha256((api_secret + str(ts)).encode()).hexdigest()}
        http = session or requests.Session()
        try:
            resp = http.post(TOKEN_URL, headers=_headers(api_key), json=body, timeout=15)
        except requests.RequestException as e:
            raise GrowwReadError(redact(f"Groww login failed: {type(e).__name__}", (api_key, totp_secret, api_secret))) from None
        if not resp.ok:
            raise GrowwReadError(f"Groww login failed (HTTP {resp.status_code})", resp.status_code)
        token = resp.json().get("token")
        if not token:
            raise GrowwReadError("Groww login returned no token")
        return cls(token, http)

    def _get(self, path: str, params: dict | None = None, retries: int = 2) -> Any:
        for attempt in range(retries + 1):
            try:
                resp = self._http.get(BASE_URL + path, params=params, headers=_headers(self._token), timeout=self._timeout)
            except requests.RequestException as e:
                if attempt == retries:
                    raise GrowwReadError(f"Groww request to {path} failed: {type(e).__name__}") from None
                time.sleep(1.5 * (attempt + 1))
                continue
            if resp.status_code in (429, 502, 503, 504) and attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            return _parse(resp)

    # --- reads only ---------------------------------------------------------
    def user_profile(self) -> dict:
        return self._get("/user/detail")

    def margin(self) -> dict:
        return self._get("/margins/detail/user")

    def positions(self, segment: str | None = None) -> dict:
        return self._get("/positions/user", {"segment": segment} if segment else None)

    def holdings(self) -> dict:
        return self._get("/holdings/user")

    def orders_page(self, segment: str, page: int, page_size: int = 25) -> list:
        return first_list(self._get("/order/list", {"segment": segment, "page": page, "page_size": page_size}))

    def all_orders_today(self, segment: str, page_size: int = 25, max_pages: int = 40) -> list:
        out = []
        for page in range(max_pages):
            rows = self.orders_page(segment, page, page_size)
            out.extend(rows)
            if len(rows) < page_size:
                break
        return out

    def fills_for_order(self, groww_order_id: str, segment: str, page_size: int = 50, max_pages: int = 20) -> list:
        out = []
        for page in range(max_pages):
            rows = first_list(self._get(f"/order/trades/{groww_order_id}",
                                        {"segment": segment, "page": page, "page_size": page_size}))
            out.extend(rows)
            if len(rows) < page_size:
                break
        return out
