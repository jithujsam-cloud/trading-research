"""Synthetic Groww-format exports. No real account data is used in tests."""

import openpyxl
import pytest

LEDGER_HEADER = ["Transaction Date", "Settlement Date", "Clearing Corporation/Clearing Member", "Segment Type",
                 "Settlement No.", "Bill/Chq No.", "Transaction Type", "Particulars / Narration", "Voucher No.",
                 "Debit (Rs.)", "Credit (Rs.)", "Balance (Rs.)"]

# chronological: (date, segment, settlement_no, txn_type, debit, credit)
LEDGER_ROWS = [
    ("01-10-2024", "UPI", "N/A", "JV", 0, 3000),
    ("01-10-2024", "STOCKS_SETTLEMENT", "X_2024186FNO", "bill", 1000, 0),   # F&O loss
    ("02-10-2024", "UPI", "N/A", "JV", 0, 1000),                             # deposit day after a loss
    ("02-10-2024", "STOCKS_SETTLEMENT", "X_2024187FNO", "bill", 0, 600),     # F&O win
    ("03-10-2024", "STOCKS_SETTLEMENT", "X_2024188FNO", "bill", 300, 0),     # F&O loss
    ("03-10-2024", "STOCKS_SETTLEMENT", "X_2024188M", "bill", 1000.40, 0),   # buy 10 @ 100 + 0.40 charges
    ("10-10-2024", "STOCKS_SETTLEMENT", "X_2024193M", "bill", 0, 1099.50),   # sell 10 @ 110 - 0.50 charges
    ("11-10-2024", "GROWW_WITHDRAW", "N/A", "Payment", 2000, 0),
]


def _ledger_rows_with_balance():
    bal, out = 0.0, []
    for d, seg, sno, typ, dr, cr in LEDGER_ROWS:
        bal = round(bal + cr - dr, 2)
        out.append((d, d, "N/A", seg, sno, "", typ, "N/A", "V", float(dr), float(cr), bal))
    return out


@pytest.fixture
def ledger_xlsx(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Client Name", "Test"])
    ws.append(["PAN", "XXXXX0000X"])
    ws.append([])
    ws.append(LEDGER_HEADER)
    for r in reversed(_ledger_rows_with_balance()):  # Groww lists newest first
        ws.append(list(r))
    ws.append([])
    ws.append(["Note - computer generated statement"])
    p = tmp_path / "ledger.xlsx"
    wb.save(p)
    return p


ORDER_HEADER = ["Stock name", "Symbol", "ISIN", "Type", "Quantity", "Value", "Exchange",
                "Exchange Order Id", "Execution date and time", "Order status"]

ORDERS = [
    ("ABC", "BUY", 10, 1000.0, "03-10-2024 10:00 AM", "Executed"),
    ("ABC", "SELL", 10, 1100.0, "10-10-2024 11:00 AM", "Executed"),
    ("XYZ", "SELL", 5, 500.0, "04-10-2024 09:20 AM", "Executed"),   # intraday short
    ("XYZ", "BUY", 5, 490.0, "04-10-2024 09:40 AM", "Executed"),
    ("XYZ", "BUY", 3, 300.0, "05-10-2024 09:40 AM", "Cancelled"),
]


@pytest.fixture
def orders_xlsx(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Name", "Test"])
    ws.append([])
    ws.append(ORDER_HEADER)
    for sym, side, q, v, t, st in ORDERS:
        ws.append([sym + " LTD", sym, "INE000000000", side, q, v, "NSE", "1", t, st])
    p = tmp_path / "orders.xlsx"
    wb.save(p)
    return p
