"""Daily read-only snapshot: Groww keeps only today's orders, so save them every evening.

Saves today's orders and their fills (both segments), positions and funds, and
refreshes the Nifty option lot size from Groww's public instrument file.
"""

import hashlib
import io
import json
from datetime import datetime, timedelta, timezone

from ..broker.rest import INSTRUMENT_CSV_URL, GrowwReadClient
from .db import SupabaseStore

IST = timezone(timedelta(hours=5, minutes=30))


def _order_id(o: dict) -> str | None:
    return o.get("groww_order_id") or o.get("order_id")


def _fill_id(f: dict) -> str:
    fid = f.get("groww_trade_id") or f.get("trade_id") or f.get("exchange_trade_id")
    if fid:
        return str(fid)
    return hashlib.sha256(json.dumps(f, sort_keys=True, default=str).encode()).hexdigest()[:32]


def _filled_qty(o: dict) -> float:
    for k in ("filled_quantity", "filled_qty", "executed_quantity"):
        if o.get(k) is not None:
            try:
                return float(o[k])
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def nifty_lot_size(http_get=None) -> int | None:
    """Read the current NIFTY option lot size from Groww's public instrument file."""
    import pandas as pd
    import requests
    get = http_get or (lambda url: requests.get(url, timeout=60))
    resp = get(INSTRUMENT_CSV_URL)
    resp.raise_for_status()
    d = pd.read_csv(io.BytesIO(resp.content), low_memory=False, usecols=["underlying_symbol", "instrument_type", "lot_size"])
    sizes = d[(d["underlying_symbol"] == "NIFTY") & d["instrument_type"].isin(["CE", "PE"])]["lot_size"].dropna().unique()
    return int(sizes[0]) if len(sizes) == 1 else None


def run_snapshot(groww: GrowwReadClient, store: SupabaseStore, now: datetime | None = None, lot_size_fn=nifty_lot_size) -> dict:
    now = now or datetime.now(IST)
    today = now.date().isoformat()
    details = {"orders": 0, "fills": 0, "errors": []}
    started = now.isoformat()

    for segment in ("CASH", "FNO"):
        try:
            orders = groww.all_orders_today(segment)
        except Exception as e:  # keep going: one failed segment should not lose the rest
            details["errors"].append(f"orders {segment}: {e}")
            continue
        rows = [{"groww_order_id": _order_id(o), "segment": segment, "trade_date": today,
                 "status": o.get("order_status"), "payload": o, "last_seen_at": now.isoformat()}
                for o in orders if _order_id(o)]
        store.upsert("broker_orders", rows, "groww_order_id")
        details["orders"] += len(rows)
        for o in orders:
            if _filled_qty(o) <= 0 or not _order_id(o):
                continue
            try:
                fills = groww.fills_for_order(_order_id(o), segment)
            except Exception as e:
                details["errors"].append(f"fills {_order_id(o)}: {e}")
                continue
            store.upsert("broker_fills", [{"fill_id": _fill_id(f), "groww_order_id": _order_id(o), "segment": segment,
                                           "payload": f} for f in fills], "fill_id")
            details["fills"] += len(fills)

    for kind, fn in (("positions", groww.positions), ("margin", groww.margin)):
        try:
            store.insert("broker_snapshots", {"kind": kind, "taken_at": now.isoformat(), "payload": fn()})
        except Exception as e:
            details["errors"].append(f"{kind}: {e}")

    try:
        lot = lot_size_fn()
        if lot:
            store.upsert("settings", [{"key": "nifty_lot_size", "value": {"lot_size": lot, "as_of": today},
                                       "updated_at": now.isoformat()}], "key")
            details["nifty_lot_size"] = lot
    except Exception as e:
        details["errors"].append(f"lot size: {type(e).__name__}")

    status = "ok" if not details["errors"] else "partial"
    store.insert("snapshot_runs", {"started_at": started, "finished_at": datetime.now(IST).isoformat(),
                                   "status": status, "details": details})
    return {"status": status, **details}
