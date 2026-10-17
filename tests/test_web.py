import re
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tradelab.broker import rest
from tradelab.web import app as webapp
from tradelab.web import auth
from tradelab.web.render import markdown_html
from tradelab.web.snapshot import IST, run_snapshot

SECRET = "s" * 40


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "correct horse")
    monkeypatch.setenv("SESSION_SECRET", SECRET)
    monkeypatch.setenv("CRON_SECRET", "cron-secret")
    for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "GROWW_API_KEY", "GROWW_TOTP_SECRET", "GROWW_API_SECRET"):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture
def client(env, monkeypatch):
    monkeypatch.setattr(webapp.asyncio, "sleep", lambda s: _noop())
    return TestClient(webapp.app, base_url="https://testserver")


async def _noop():
    return None


def login(c):
    r = c.post("/login", data={"password": "correct horse"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"
    return r


# --- auth -------------------------------------------------------------------

def test_unconfigured_app_refuses_to_serve(monkeypatch):
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    c = TestClient(webapp.app, base_url="https://testserver")
    assert c.get("/").status_code == 503


def test_pages_need_login(client):
    for path in ["/", "/report", "/upload", "/viability", "/snapshots"]:
        r = client.get(path, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/login"


def test_wrong_password_rejected(client):
    r = client.post("/login", data={"password": "nope"}, follow_redirects=False)
    assert r.headers["location"] == "/login?error=1"
    assert auth.COOKIE not in r.cookies


def test_session_cookie_is_signed_and_expires(env):
    s = auth.make_session(now=1000)
    assert auth.session_ok(s, now=1001)
    assert not auth.session_ok(s, now=1000 + auth.SESSION_SECONDS + 1)
    expiry, sig = s.split(".")
    assert not auth.session_ok(f"{int(expiry) + 999}.{sig}", now=1001)


def test_login_sets_secure_httponly_cookie(client):
    r = login(client)
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "secure" in cookie and "samesite=lax" in cookie
    assert client.get("/").status_code == 200


def test_security_headers(client):
    h = client.get("/login").headers
    assert "frame-ancestors 'none'" in h["content-security-policy"]
    assert h["cache-control"] == "no-store"


def test_health_reveals_no_secrets(client):
    body = client.get("/health").text
    assert "correct horse" not in body and SECRET not in body and "cron-secret" not in body


# --- pages ------------------------------------------------------------------

def test_upload_runs_analysis_without_database(client, ledger_xlsx, orders_xlsx):
    login(client)
    files = {"ledger": ("l.xlsx", Path(ledger_xlsx).read_bytes()), "orders": ("o.xlsx", Path(orders_xlsx).read_bytes())}
    r = client.post("/upload", files=files)
    assert r.status_code == 200
    assert "no edge demonstrated" in r.text and "<table>" in r.text


def test_upload_rejects_non_xlsx(client):
    login(client)
    r = client.post("/upload", files={"ledger": ("l.xlsx", b"hello"), "orders": ("o.xlsx", b"hello")})
    assert r.status_code == 400 and "not an .xlsx" in r.text


def test_viability_page(client):
    login(client)
    r = client.get("/viability?capital=4000")
    assert r.status_code == 200 and "Capital ₹4,000" in r.text and "Lot size 65" in r.text


def test_markdown_escapes_data():
    out = markdown_html("| a |\n|---|\n| <script>alert(1)</script> |")
    assert "<script>" not in out and "&lt;script&gt;" in out


# --- cron -------------------------------------------------------------------

def test_cron_requires_secret(client):
    assert client.get("/api/cron/snapshot").status_code == 401
    assert client.get("/api/cron/snapshot", headers={"Authorization": "Bearer wrong"}).status_code == 401


class FakeStore:
    def __init__(self):
        self.rows = {}

    def insert(self, table, rows):
        self.rows.setdefault(table, []).extend(rows if isinstance(rows, list) else [rows])

    def upsert(self, table, rows, on_conflict):
        self.rows.setdefault(table, []).extend(rows)


class FakeGroww:
    def all_orders_today(self, segment):
        if segment == "FNO":
            return [{"groww_order_id": "G1", "order_status": "EXECUTED", "filled_quantity": 65},
                    {"groww_order_id": "G2", "order_status": "REJECTED", "filled_quantity": 0}]
        return []

    def fills_for_order(self, oid, segment):
        return [{"groww_trade_id": "T1", "price": 100}, {"groww_trade_id": "T2", "price": 101}]

    def positions(self):
        return {"positions": []}

    def margin(self):
        raise rest.GrowwReadError("timeout")


def test_snapshot_saves_orders_fills_and_records_problems():
    store = FakeStore()
    out = run_snapshot(FakeGroww(), store, now=datetime(2026, 10, 19, 16, 15, tzinfo=IST), lot_size_fn=lambda: 65)
    assert out["orders"] == 2 and out["fills"] == 2  # fills fetched only for the filled order
    assert out["status"] == "partial" and any("margin" in e for e in out["errors"])
    assert {r["fill_id"] for r in store.rows["broker_fills"]} == {"T1", "T2"}
    assert store.rows["broker_orders"][0]["trade_date"] == "2026-10-19"
    assert store.rows["settings"][0]["value"]["lot_size"] == 65
    assert store.rows["snapshot_runs"][0]["status"] == "partial"


# --- read-only client ---------------------------------------------------------

def test_rest_client_has_no_order_writing_code():
    src = Path(rest.__file__).read_text()
    for forbidden in ["/order/create", "/order/modify", "/order/cancel", "order-advance", ".post(BASE_URL", ".put(", ".delete("]:
        assert forbidden not in src
    # the only POST is the login call
    assert len(re.findall(r"\.post\(", src)) == 1 and "TOKEN_URL" in src


def test_totp_matches_rfc6238_vector():
    import base64
    secret = base64.b32encode(b"12345678901234567890").decode()
    assert rest.totp_now(secret, at=59, digits=8) == "94287082"
    assert rest.totp_now(secret, at=1111111109, digits=8) == "07081804"
