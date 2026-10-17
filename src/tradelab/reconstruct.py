"""Rebuild closed round trips from executed orders, first in, first out.

Label: DERIVED. The order export has one row per order with its total executed
value; it has no fill-level detail and no charges, so profits here are gross.
A short sale (sell before buy, same symbol) is matched the same way.
"""

from collections import defaultdict, deque

import pandas as pd


TRADE_COLUMNS = ["trade_id", "symbol", "direction", "qty", "opened", "closed", "entry_price", "exit_price",
                 "gross_pnl", "hold_days", "hold_minutes"]


def round_trips(orders: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (closed_trades, open_lots).

    closed_trades columns: trade_id, symbol, direction, qty, opened, closed,
    entry_price, exit_price, gross_pnl, hold_days, hold_minutes.
    """
    lots: dict[str, deque] = defaultdict(deque)  # symbol -> deque of [signed_qty, price, time]
    closed = []
    for o in orders.sort_values("time", kind="stable").itertuples(index=False):
        sign = 1 if o.side == "BUY" else -1
        qty = float(o.qty)
        book = lots[o.symbol]
        while qty > 1e-9 and book and book[0][0] * sign < 0:
            lot_qty, lot_price, lot_time = book[0]
            matched = min(qty, abs(lot_qty))
            long_trade = lot_qty > 0
            entry, exit_ = lot_price, o.price
            pnl = (exit_ - entry) * matched if long_trade else (entry - exit_) * matched
            closed.append({
                "symbol": o.symbol,
                "direction": "long" if long_trade else "short",
                "qty": matched,
                "opened": lot_time,
                "closed": o.time,
                "entry_price": entry,
                "exit_price": exit_,
                "gross_pnl": round(pnl, 2),
                "hold_days": (o.time.date() - lot_time.date()).days,
                "hold_minutes": round((o.time - lot_time).total_seconds() / 60),
            })
            qty -= matched
            remaining = lot_qty + sign * matched
            if abs(remaining) < 1e-9:
                book.popleft()
            else:
                book[0][0] = remaining
        if qty > 1e-9:
            book.append([sign * qty, o.price, o.time])

    trades = pd.DataFrame.from_records(closed, columns=TRADE_COLUMNS[1:])
    trades.insert(0, "trade_id", range(1, len(trades) + 1))
    open_rows = [
        {"symbol": s, "qty": q, "price": p, "opened": t}
        for s, book in lots.items() for q, p, t in book
    ]
    return trades, pd.DataFrame.from_records(open_rows, columns=["symbol", "qty", "price", "opened"])
