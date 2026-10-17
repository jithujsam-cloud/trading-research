from datetime import date

from tradelab.ingest import LedgerKind, load_ledger, load_stock_orders
from tradelab.ingest.groww_ledger import _repair_same_day_order


def test_ledger_restores_chronology_and_reconciles(ledger_xlsx):
    df, msgs = load_ledger(ledger_xlsx)
    assert msgs == []
    assert df["date"].iloc[0] == date(2024, 10, 1)
    assert df["balance_check_ok"].all()
    assert df["seq"].tolist() == list(range(1, len(df) + 1))


def test_ledger_classification(ledger_xlsx):
    df, _ = load_ledger(ledger_xlsx)
    counts = df["kind"].value_counts().to_dict()
    assert counts[LedgerKind.DEPOSIT.value] == 2
    assert counts[LedgerKind.WITHDRAWAL.value] == 1
    assert counts[LedgerKind.FNO_SETTLEMENT.value] == 3
    assert counts[LedgerKind.EQUITY_SETTLEMENT.value] == 2


def test_ledger_never_returns_personal_metadata(ledger_xlsx):
    df, _ = load_ledger(ledger_xlsx)
    assert "PAN" not in " ".join(map(str, df.columns))
    assert not df.astype(str).apply(lambda c: c.str.contains("XXXXX0000X")).any().any()


def test_same_day_reorder_only_when_balance_proves_it():
    rows = [
        {"date": date(2024, 9, 27), "amount": 100.0, "balance": 100.0},
        # listed out of order: the withdrawal of 30 came before the bill of -20
        {"date": date(2024, 9, 30), "amount": -20.0, "balance": 50.0},
        {"date": date(2024, 9, 30), "amount": -30.0, "balance": 70.0},
    ]
    msgs = []
    fixed = _repair_same_day_order(rows, msgs)
    assert [r["amount"] for r in fixed] == [100.0, -30.0, -20.0]
    assert len(msgs) == 1
    # amounts and balances are never altered
    assert sorted(r["balance"] for r in fixed) == [50.0, 70.0, 100.0]


def test_orders_keep_only_executed(orders_xlsx):
    df, msgs = load_stock_orders(orders_xlsx)
    assert len(df) == 4
    assert any("not executed" in m for m in msgs)
    assert df["time"].is_monotonic_increasing
    assert df.loc[0, "price"] == 100.0
