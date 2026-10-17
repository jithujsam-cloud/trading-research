"""The history pipeline shared by the command line and the web app."""

from pathlib import Path

from .history import analyze
from .ingest import load_ledger, load_stock_orders
from .reconstruct import round_trips


def run_history(ledger_path: str | Path, orders_path: str | Path, seed: int = 7) -> tuple[dict, dict]:
    """Import both exports and analyse them. Returns (result, clean_tables)."""
    ledger, v1 = load_ledger(ledger_path)
    orders, v2 = load_stock_orders(orders_path)
    trades, open_lots = round_trips(orders)
    validation = v1 + v2
    if not open_lots.empty:
        validation.append(f"{len(open_lots)} open stock lot(s) left unmatched (still held or bought before the export): "
                          + ", ".join(sorted(open_lots["symbol"].unique())))
    result = analyze(ledger, orders, trades, seed=seed)
    result["validation"] = validation
    tables = {"ledger": ledger, "stock_orders": orders, "stock_round_trips": trades, "stock_open_lots": open_lots}
    return result, tables
