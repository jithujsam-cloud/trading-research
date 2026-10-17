from datetime import datetime

import pandas as pd

from tradelab.reconstruct import round_trips


def orders(rows):
    return pd.DataFrame([{"time": datetime.fromisoformat(t), "symbol": s, "side": side, "qty": q, "price": p, "value": q * p}
                         for t, s, side, q, p in rows])


def test_fifo_long_with_partial_exits():
    t, open_lots = round_trips(orders([
        ("2024-01-01 10:00", "A", "BUY", 10, 100),
        ("2024-01-02 10:00", "A", "BUY", 10, 110),
        ("2024-01-05 10:00", "A", "SELL", 15, 120),
    ]))
    assert t["qty"].tolist() == [10, 5]
    assert t["gross_pnl"].tolist() == [200.0, 50.0]   # first lot first
    assert t["hold_days"].tolist() == [4, 3]
    assert open_lots.iloc[0]["qty"] == 5 and open_lots.iloc[0]["price"] == 110


def test_intraday_short_is_matched():
    t, open_lots = round_trips(orders([
        ("2024-01-01 09:20", "B", "SELL", 5, 100),
        ("2024-01-01 09:50", "B", "BUY", 5, 98),
    ]))
    assert t.iloc[0]["direction"] == "short"
    assert t.iloc[0]["gross_pnl"] == 10.0
    assert t.iloc[0]["hold_minutes"] == 30
    assert open_lots.empty


def test_flip_from_long_to_short_in_one_order():
    t, open_lots = round_trips(orders([
        ("2024-01-01 10:00", "C", "BUY", 2, 50),
        ("2024-01-01 10:05", "C", "SELL", 5, 55),
        ("2024-01-01 10:30", "C", "BUY", 3, 54),
    ]))
    assert t["gross_pnl"].tolist() == [10.0, 3.0]
    assert open_lots.empty


def test_symbols_are_independent():
    t, _ = round_trips(orders([
        ("2024-01-01 10:00", "A", "BUY", 1, 100),
        ("2024-01-01 10:01", "B", "SELL", 1, 100),
        ("2024-01-01 10:02", "A", "SELL", 1, 90),
    ]))
    assert len(t) == 1 and t.iloc[0]["symbol"] == "A"
