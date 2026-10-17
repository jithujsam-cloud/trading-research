"""Groww 'Balance Statement' (client fund ledger) importer.

The export lists entries newest first. We restore chronological order by
reversing the file and then check that the running balance reconciles row by
row, so a reordering problem shows up as a validation failure instead of
silently wrong numbers.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path

import pandas as pd

from ._xlsx import read_table

DEPOSIT_CHANNELS = {"UPI", "GROWW_UPI", "DIRECT_NETBANKING", "RAZORPAY_DEPOSIT", "NEFT", "IMPS", "RTGS"}


class LedgerKind(str, Enum):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    FNO_SETTLEMENT = "fno_settlement"        # daily net F&O bill (amount includes charges)
    EQUITY_SETTLEMENT = "equity_settlement"  # net cash for stock buys/sells that day
    OTHER_DEBIT = "other_debit"              # e.g. STOCK_PAYOUT
    UNKNOWN = "unknown"


def classify(segment: str, txn_type: str, settlement_no: str) -> LedgerKind:
    segment = (segment or "").strip().upper()
    txn_type = (txn_type or "").strip().lower()
    settlement_no = (settlement_no or "").strip().upper()
    if segment == "GROWW_WITHDRAW":
        return LedgerKind.WITHDRAWAL
    if segment in DEPOSIT_CHANNELS or txn_type in {"reciept", "receipt"}:
        return LedgerKind.DEPOSIT
    if segment == "STOCKS_SETTLEMENT":
        if settlement_no.endswith("FNO"):
            return LedgerKind.FNO_SETTLEMENT
        if settlement_no.endswith("M"):
            return LedgerKind.EQUITY_SETTLEMENT
    if segment == "STOCK_PAYOUT":
        return LedgerKind.OTHER_DEBIT
    return LedgerKind.UNKNOWN


def _num(v) -> float:
    if v is None or v == "":
        return 0.0
    return float(str(v).replace(",", ""))


def _reconciles(prev_balance: float | None, rows: list[dict]) -> bool:
    for r in rows:
        if prev_balance is not None and abs(prev_balance + r["amount"] - r["balance"]) > 0.02:
            return False
        prev_balance = r["balance"]
    return True


def _repair_same_day_order(records: list[dict], messages: list[str], max_block: int = 8) -> list[dict]:
    """The export sometimes lists same-day entries out of order. Where a run of rows sharing
    one transaction date fails to reconcile, try the orderings of that run and keep the one
    whose running balance reconciles. Amounts are never changed; only order within a day."""
    from itertools import permutations

    out: list[dict] = []
    i = 0
    while i < len(records):
        j = i
        while j < len(records) and records[j]["date"] == records[i]["date"]:
            j += 1
        block = records[i:j]
        prev = out[-1]["balance"] if out else None
        nxt = records[j] if j < len(records) else None
        tail_ok = lambda b: nxt is None or abs(b[-1]["balance"] + nxt["amount"] - nxt["balance"]) <= 0.02  # noqa: E731
        if not (_reconciles(prev, block) and tail_ok(block)) and len(block) <= max_block:
            for perm in permutations(block):
                if _reconciles(prev, list(perm)) and tail_ok(perm):
                    messages.append(f"reordered {len(block)} entries dated {block[0]['date']} so the running balance reconciles")
                    block = list(perm)
                    break
        out.extend(block)
        i = j
    return out


def load_ledger(path: str | Path) -> tuple[pd.DataFrame, list[str]]:
    """Load the ledger. Returns (frame, validation_messages).

    Columns: seq, date, settlement_date, kind, segment, settlement_no, debit, credit,
    amount (credit - debit), balance, balance_check_ok.
    """
    header, rows = read_table(path, "Transaction Date")
    idx = {name: i for i, name in enumerate(header)}
    need = ["Transaction Date", "Settlement Date", "Segment Type", "Settlement No.",
            "Transaction Type", "Debit (Rs.)", "Credit (Rs.)", "Balance (Rs.)"]
    missing = [c for c in need if c not in idx]
    if missing:
        raise ValueError(f"ledger is missing columns: {missing}")

    records = []
    for r in reversed(rows):  # file is newest first
        get = lambda c: r[idx[c]]  # noqa: E731
        debit, credit = _num(get("Debit (Rs.)")), _num(get("Credit (Rs.)"))
        records.append({
            "date": datetime.strptime(str(get("Transaction Date")).strip(), "%d-%m-%Y").date(),
            "settlement_date": datetime.strptime(str(get("Settlement Date")).strip(), "%d-%m-%Y").date(),
            "segment": str(get("Segment Type") or ""),
            "settlement_no": str(get("Settlement No.") or ""),
            "kind": classify(get("Segment Type"), get("Transaction Type"), get("Settlement No.")).value,
            "debit": debit,
            "credit": credit,
            "amount": round(credit - debit, 2),
            "balance": _num(get("Balance (Rs.)")),
        })
    messages: list[str] = []
    records = _repair_same_day_order(records, messages)
    df = pd.DataFrame.from_records(records)
    df.insert(0, "seq", range(1, len(df) + 1))

    prev = df["balance"].shift(1)
    expected = (prev + df["amount"]).round(2)
    ok = (expected - df["balance"]).abs() <= 0.02
    ok.iloc[0] = True  # opening row has no predecessor in this file
    df["balance_check_ok"] = ok
    bad = int((~ok).sum())
    if bad:
        messages.append(f"{bad} ledger rows do not reconcile with the previous running balance")
    unknown = int((df["kind"] == LedgerKind.UNKNOWN.value).sum())
    if unknown:
        messages.append(f"{unknown} ledger rows have an unrecognised type and are excluded from totals")
    return df, messages
