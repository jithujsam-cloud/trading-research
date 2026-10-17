"""Storage in Supabase through its REST API, using the service-role key server-side only.

Tables are created by supabase/migrations/*.sql with row-level security on and
no policies, so the public anon key cannot read them.
"""

import os
from typing import Any

import requests


class StoreError(RuntimeError):
    pass


class SupabaseStore:
    def __init__(self, url: str, key: str, session: requests.Session | None = None, timeout: float = 15.0):
        self._base = url.rstrip("/") + "/rest/v1/"
        self._key = key
        self._http = session or requests.Session()
        self._timeout = timeout

    def __repr__(self) -> str:
        return "SupabaseStore(<key hidden>)"

    @classmethod
    def from_env(cls) -> "SupabaseStore | None":
        url, key = os.environ.get("SUPABASE_URL", ""), os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        return cls(url, key) if url and key else None

    def _headers(self, prefer: str | None = None) -> dict:
        h = {"apikey": self._key, "Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}
        if prefer:
            h["Prefer"] = prefer
        return h

    def _check(self, resp: requests.Response, what: str) -> requests.Response:
        if not resp.ok:
            raise StoreError(f"database {what} failed (HTTP {resp.status_code})")
        return resp

    def insert(self, table: str, rows: list[dict] | dict) -> None:
        if not rows:
            return
        r = self._http.post(self._base + table, json=rows, headers=self._headers("return=minimal"), timeout=self._timeout)
        self._check(r, f"insert into {table}")

    def upsert(self, table: str, rows: list[dict], on_conflict: str) -> None:
        if not rows:
            return
        r = self._http.post(self._base + table, params={"on_conflict": on_conflict}, json=rows,
                            headers=self._headers("resolution=merge-duplicates,return=minimal"), timeout=self._timeout)
        self._check(r, f"upsert into {table}")

    def latest(self, table: str, order_col: str, limit: int = 1, filters: dict | None = None) -> list[dict[str, Any]]:
        params = {"select": "*", "order": f"{order_col}.desc", "limit": str(limit)}
        params.update(filters or {})
        r = self._http.get(self._base + table, params=params, headers=self._headers(), timeout=self._timeout)
        return self._check(r, f"read from {table}").json()
