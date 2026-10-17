"""FastAPI app served on Vercel from api/index.py.

Read-only by design: it analyses uploaded statements, shows stored results and
runs the daily snapshot. It has no route or client method that can trade.
"""

import asyncio
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .. import report as md_report
from ..broker.readonly import redact
from ..broker.rest import GrowwReadClient
from ..costs import CostModel
from ..pipeline import run_history
from ..viability import grid
from . import auth
from .db import SupabaseStore
from .render import esc, markdown_html, page, rupees, signed_class
from .snapshot import run_snapshot

DEFAULT_LOT_SIZE = 65
MAX_UPLOAD_BYTES = 4 * 1024 * 1024

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Cache-Control"] = "no-store"
    return resp


def _store() -> SupabaseStore | None:
    return SupabaseStore.from_env()


def _guard(request: Request):
    """Return a response to send instead of the page, or None when the visitor is logged in."""
    if not auth.configured():
        return HTMLResponse(page("Not configured", '<div class="card"><h1>Not configured</h1><p>Set APP_PASSWORD and a '
                                 'SESSION_SECRET of at least 32 characters in Vercel, then redeploy.</p></div>', logged_in=False), 503)
    if not auth.session_ok(request.cookies.get(auth.COOKIE)):
        return RedirectResponse("/login", 303)
    return None


def _error_card(msg: str) -> str:
    return f'<div class="card"><p class="bad">{esc(redact(msg))}</p></div>'


@app.get("/health")
def health():
    return {"ok": True, "login_configured": auth.configured(), "database_configured": _store() is not None,
            "groww_configured": bool(os.environ.get("GROWW_API_KEY")), "cron_configured": bool(os.environ.get("CRON_SECRET"))}


@app.get("/login", response_class=HTMLResponse)
def login_form(error: str = ""):
    msg = '<p class="bad">That password is not right.</p>' if error else ""
    body = (f'<div class="card"><h1>Log in</h1>{msg}<form method="post" action="/login">'
            '<label for="pw">Password<input id="pw" name="password" type="password" autocomplete="current-password" required></label>'
            '<button type="submit">Log in</button></form></div>')
    return page("Log in", body, logged_in=False)


@app.post("/login")
async def login(password: str = Form(...)):
    if not auth.configured():
        return RedirectResponse("/", 303)
    if not auth.password_ok(password):
        await asyncio.sleep(1.0)  # slow down guessing
        return RedirectResponse("/login?error=1", 303)
    resp = RedirectResponse("/", 303)
    resp.set_cookie(auth.COOKIE, auth.make_session(), max_age=auth.SESSION_SECONDS, httponly=True, secure=True, samesite="lax")
    return resp


@app.post("/logout")
def logout():
    resp = RedirectResponse("/login", 303)
    resp.delete_cookie(auth.COOKIE)
    return resp


def _latest(store, table, order_col, **filters):
    try:
        rows = store.latest(table, order_col, 1, filters) if store else []
        return rows[0] if rows else None
    except Exception:
        return None


@app.get("/", response_class=HTMLResponse)
def overview(request: Request):
    if (g := _guard(request)):
        return g
    store = _store()
    rep = _latest(store, "history_reports", "created_at")
    run = _latest(store, "snapshot_runs", "started_at")
    tiles = []
    if rep:
        r = rep["report"]
        fno = r.get("fno", {}).get("summary", {}).get("total", {}).get("value")
        net = r.get("stocks", {}).get("net_in_ledger_period", {}).get("value", {}).get("net")
        tiles += [("F&O net result", rupees(fno), signed_class(fno), "verified daily bills"),
                  ("Stocks, net of implied charges", rupees(net), signed_class(net), "derived")]
        verdicts = "".join(f"<li><b>{esc(v['segment'])}:</b> {'edge shown' if v['edge_demonstrated'] else 'no edge demonstrated'}</li>"
                           for v in r.get("edge_verdict", []))
    else:
        verdicts = "<li>No history report yet. Upload your Groww statements.</li>"
    if run:
        cls = "ok" if run["status"] == "ok" else "warn"
        tiles.append(("Last snapshot", esc(str(run["started_at"])[:16].replace("T", " ")), cls, esc(run["status"])))
    else:
        tiles.append(("Last snapshot", "none yet", "muted", "runs on weekday evenings"))
    tile_html = "".join(f'<div class="card"><div class="k">{esc(k)}</div><div class="v {c}">{v}</div><div class="k">{esc(n)}</div></div>'
                        for k, v, c, n in tiles)
    notes = "" if store else '<p class="warn">No database connected: reports are shown once and not saved.</p>'
    body = (f'<h1>Overview</h1>{notes}<div class="grid">{tile_html}</div>'
            f'<div class="card"><h2 style="margin-top:0">Is there an edge?</h2><ul>{verdicts}</ul>'
            '<p class="muted">Live order placement is not part of this system. It stays off until a strategy passes the go-live criteria.</p></div>')
    return page("Overview", body, "/")


@app.get("/report", response_class=HTMLResponse)
def latest_report(request: Request):
    if (g := _guard(request)):
        return g
    rep = _latest(_store(), "history_reports", "created_at")
    if not rep:
        return page("History report", '<div class="card"><h1>No report yet</h1><p><a href="/upload">Upload your statements</a> to create one.</p></div>', "/report")
    r = rep["report"]
    return page("History report", f'<div class="card report">{markdown_html(md_report.history_markdown(r, r.get("validation", [])))}</div>', "/report")


@app.get("/upload", response_class=HTMLResponse)
def upload_form(request: Request):
    if (g := _guard(request)):
        return g
    body = ('<div class="card"><h1>Upload statements</h1><p>From Groww: the Balance Statement and the Stocks Order History, as .xlsx. '
            'The files are analysed in memory and not kept; only the resulting report is saved.</p>'
            '<form method="post" action="/upload" enctype="multipart/form-data">'
            '<label for="ledger">Balance statement (.xlsx)<input id="ledger" name="ledger" type="file" accept=".xlsx" required></label>'
            '<label for="orders">Stocks order history (.xlsx)<input id="orders" name="orders" type="file" accept=".xlsx" required></label>'
            '<button type="submit">Analyse</button></form></div>')
    return page("Upload statements", body, "/upload")


async def _read_xlsx(f: UploadFile) -> bytes:
    data = await f.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(f"{f.filename} is larger than 4 MB")
    if not data.startswith(b"PK"):
        raise ValueError(f"{f.filename} is not an .xlsx file")
    return data


@app.post("/upload", response_class=HTMLResponse)
async def upload(request: Request, ledger: UploadFile = File(...), orders: UploadFile = File(...)):
    if (g := _guard(request)):
        return g
    try:
        ledger_bytes, orders_bytes = await _read_xlsx(ledger), await _read_xlsx(orders)
        with tempfile.TemporaryDirectory() as tmp:
            lp, op = Path(tmp) / "ledger.xlsx", Path(tmp) / "orders.xlsx"
            lp.write_bytes(ledger_bytes)
            op.write_bytes(orders_bytes)
            result, _ = run_history(lp, op)
    except Exception as e:
        return HTMLResponse(page("Upload statements", _error_card(f"Could not read the files: {e}"), "/upload"), 400)
    saved = ""
    store = _store()
    if store:
        try:
            store.insert("history_reports", {"report": result})
            saved = '<p class="ok">Report saved.</p>'
        except Exception as e:
            saved = f'<p class="warn">Report shown but not saved: {esc(redact(str(e)))}</p>'
    body = f'{saved}<div class="card report">{markdown_html(md_report.history_markdown(result, result["validation"]))}</div>'
    return page("History report", body, "/upload")


def _lot_size() -> tuple[int, str]:
    row = _latest(_store(), "settings", "updated_at", key="eq.nifty_lot_size")
    if row and row.get("value", {}).get("lot_size"):
        v = row["value"]
        return int(v["lot_size"]), f"from Groww's instrument file, {v.get('as_of')}"
    return DEFAULT_LOT_SIZE, "default (17 Oct 2026); updated by the daily snapshot once connected"


@app.get("/viability", response_class=HTMLResponse)
def viability(request: Request, capital: float = 16000, risk_limit: float = 0.02):
    if (g := _guard(request)):
        return g
    capital = max(500.0, min(capital, 1e8))
    risk_limit = max(0.001, min(risk_limit, 0.1))
    lot, source = _lot_size()
    from datetime import date
    on = str(date.today())
    rows = [r.as_dict() for r in grid([capital], [5, 10, 20, 50, 100, 150, 200], [0.2, 0.35], lot, on, CostModel(), risk_limit)]
    form = (f'<form method="get" action="/viability"><label for="capital">Trading capital (₹)'
            f'<input id="capital" name="capital" type="number" min="500" step="500" value="{capital:.0f}"></label>'
            f'<label for="risk">Risk per trade (fraction, 0.02 = 2%)<input id="risk" name="risk_limit" type="number" step="0.005" min="0.001" max="0.1" value="{risk_limit}"></label>'
            '<button type="submit">Recalculate</button></form>')
    table = markdown_html(md_report.viability_markdown(rows, lot, source, on, risk_limit))
    return page("Option viability", f'<div class="card">{form}</div><div class="card report">{table}</div>', "/viability")


@app.get("/snapshots", response_class=HTMLResponse)
def snapshots(request: Request):
    if (g := _guard(request)):
        return g
    store = _store()
    if not store:
        return page("Daily snapshots", '<div class="card"><h1>No database connected</h1><p>Snapshots need Supabase. See docs/07-deploy-vercel.md.</p></div>', "/snapshots")
    try:
        runs = store.latest("snapshot_runs", "started_at", 15)
    except Exception as e:
        return page("Daily snapshots", _error_card(str(e)), "/snapshots")
    rows = "".join(
        f"<tr><td>{esc(str(r['started_at'])[:16].replace('T', ' '))}</td><td class=\"{'ok' if r['status'] == 'ok' else 'warn'}\">{esc(r['status'])}</td>"
        f"<td>{esc((r.get('details') or {}).get('orders'))}</td><td>{esc((r.get('details') or {}).get('fills'))}</td>"
        f"<td>{esc('; '.join((r.get('details') or {}).get('errors', [])) or '—')}</td></tr>" for r in runs)
    body = ('<h1>Daily snapshots</h1><p class="muted">Groww only returns today\'s orders, so these runs save them each weekday evening. Read-only.</p>'
            '<div class="card t"><table><thead><tr><th>Run</th><th>Status</th><th>Orders</th><th>Fills</th><th>Problems</th></tr></thead>'
            f'<tbody>{rows or "<tr><td colspan=5>No runs yet.</td></tr>"}</tbody></table></div>')
    return page("Daily snapshots", body, "/snapshots")


@app.get("/api/cron/snapshot")
def cron_snapshot(request: Request):
    if not auth.cron_ok(request.headers.get("authorization")):
        return JSONResponse({"error": "unauthorised"}, 401)
    store = _store()
    if not store:
        return JSONResponse({"error": "database not configured"}, 503)
    try:
        groww = GrowwReadClient.from_env()
    except Exception as e:
        store.insert("snapshot_runs", {"status": "failed", "details": {"errors": [redact(str(e))]}})
        return JSONResponse({"status": "failed", "error": redact(str(e))}, 502)
    return run_snapshot(groww, store)
