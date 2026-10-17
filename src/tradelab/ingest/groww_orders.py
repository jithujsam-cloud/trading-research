"""Groww 'Stocks Order History' importer (cash segment only; no F&O in this export)."""

from datetime import datetime
from pathlib import Path

import pandas as pd

from ._xlsx import read_table


def load_stock_orders(path: str | Path) -> tuple[pd.DataFrame, list[str]]:
    """Return (executed orders sorted by time, validation_messages).

    Columns: time, symbol, isin, side, qty, value, price, exchange, order_id.
    `value` is the order's executed value as Groww reports it; `price` = value / qty.
    """
    header, rows = read_table(path, "Stock name")
    idx = {name: i for i, name in enumerate(header)}
    records, skipped = [], 0
    for r in rows:
        status = str(r[idx["Order status"]] or "").strip().lower()
        if status != "executed":
            skipped += 1
            continue
        qty = float(r[idx["Quantity"]])
        value = float(r[idx["Value"]])
        records.append({
            "time": datetime.strptime(str(r[idx["Execution date and time"]]).strip(), "%d-%m-%Y %I:%M %p"),
            "symbol": str(r[idx["Symbol"]]).strip(),
            "isin": str(r[idx["ISIN"]] or "").strip(),
            "side": str(r[idx["Type"]]).strip().upper(),
            "qty": qty,
            "value": value,
            "price": value / qty if qty else float("nan"),
            "exchange": str(r[idx["Exchange"]] or "").strip(),
            "order_id": str(r[idx["Exchange Order Id"]] or "").strip(),
        })
    df = pd.DataFrame.from_records(records)
    messages = []
    if skipped:
        messages.append(f"{skipped} orders were not executed and are excluded")
    if not df.empty:
        bad_side = ~df["side"].isin(["BUY", "SELL"])
        if bad_side.any():
            messages.append(f"{int(bad_side.sum())} orders have an unknown side and are excluded")
            df = df[~bad_side]
        # stable sort keeps file order for orders stamped in the same minute
        df = df.sort_values("time", kind="stable").reset_index(drop=True)
    return df, messages
