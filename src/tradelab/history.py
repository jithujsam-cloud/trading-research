"""Reproducible analysis of the account's past results.

Rules this module follows:
- F&O figures come only from the ledger's daily settlement bills. No intraday
  sequence is inferred from them (they are one net number per day).
- Stock figures come from FIFO round trips of executed orders (gross of charges).
- Anything that did not happen is labelled HYPOTHETICAL and is never presented
  as evidence of an edge.
"""

from datetime import timedelta

import numpy as np
import pandas as pd

from .ingest.groww_ledger import LedgerKind
from .provenance import Label
from .stats import summarize


def m(value, label: Label, note: str = "") -> dict:
    """A labelled metric."""
    if isinstance(value, (np.floating, np.integer)):
        value = value.item()
    out = {"value": value, "label": label.value}
    if note:
        out["note"] = note
    return out


def activity_windows(dates: pd.Series, gap_days: int = 30) -> list[tuple]:
    """Split activity into windows separated by at least `gap_days` without activity."""
    ds = sorted(set(pd.to_datetime(dates).dt.date))
    windows, start, prev = [], ds[0], ds[0]
    for d in ds[1:]:
        if (d - prev).days >= gap_days:
            windows.append((start, prev))
            start = d
        prev = d
    windows.append((start, prev))
    return windows


def _fno_section(ledger: pd.DataFrame, seed: int) -> dict:
    fno = ledger[ledger["kind"] == LedgerKind.FNO_SETTLEMENT.value].copy()
    if fno.empty:
        return {"available": False}
    daily = fno.groupby("date", sort=True)["amount"].sum()
    s = summarize(daily.values, seed=seed)

    # capital available that day: the larger of the previous day's closing balance and any
    # balance reached earlier the same day (e.g. after a morning deposit), before the bill posts
    day_end = ledger.groupby("date", sort=True)["balance"].last()

    def available(row) -> float:
        earlier_days = day_end[day_end.index < row.date]
        same_day = ledger[(ledger["date"] == row.date) & (ledger["seq"] < row.seq)]["balance"]
        cands = ([float(earlier_days.iloc[-1])] if len(earlier_days) else []) + same_day.tolist()
        return max(cands) if cands else np.nan

    fno["capital_available"] = [available(r) for r in fno.itertuples()]
    fno["loss_pct_of_balance"] = np.where(
        (fno["amount"] < 0) & (fno["capital_available"] > 0), -fno["amount"] / fno["capital_available"], np.nan)

    x = daily.values
    cap = lambda lo, hi: float(np.clip(x, lo, hi).sum())  # noqa: E731
    top2 = np.sort(x)[::-1][:2]
    hypo = {
        "assumption": ("Same trading days; a daily cap is assumed to fill exactly at the cap. "
                       "Real stops can fill worse, and a cap changes behaviour, so these are not evidence."),
        "actual": float(x.sum()),
        "stop_after_plus_500": cap(-np.inf, 500),
        "stop_at_minus_1000": cap(-1000, np.inf),
        "stop_at_minus_500": cap(-500, np.inf),
        "stop_at_both_500": cap(-500, 500),
        "stop_at_minus_500_without_best_2_days": cap(-500, np.inf) - float(top2[top2 > 0].sum()),
    }

    # behaviour: what happened the session after a winning vs losing F&O day
    after_win = [x[i + 1] for i in range(len(x) - 1) if x[i] > 0]
    after_loss = [x[i + 1] for i in range(len(x) - 1) if x[i] < 0]

    episodes = []
    for a, b in activity_windows(pd.Series(pd.to_datetime(daily.index))):
        seg = daily[(daily.index >= a) & (daily.index <= b)]
        episodes.append({"from": str(a), "to": str(b), "days": int(len(seg)), "result": float(seg.sum())})

    return {
        "available": True,
        "summary": {k: m(v, Label.DERIVED) for k, v in s.as_dict().items()},
        "daily": [{"date": str(d), "amount": float(v), "label": Label.VERIFIED.value} for d, v in daily.items()],
        "episodes": episodes,
        "days_at_or_above_500": m(int((x >= 500).sum()), Label.DERIVED),
        "days_at_or_below_minus_500": m(int((x <= -500).sum()), Label.DERIVED),
        "worst_loss_pct_of_balance": m(float(np.nanmax(fno["loss_pct_of_balance"])) if fno["loss_pct_of_balance"].notna().any() else None,
                                       Label.DERIVED, "Loss divided by the most cash available that day before the bill posted (previous close or a same-day deposit)."),
        "median_loss_pct_of_balance": m(float(np.nanmedian(fno["loss_pct_of_balance"])) if fno["loss_pct_of_balance"].notna().any() else None,
                                        Label.DERIVED),
        "next_day_after_win": m({"n": len(after_win), "total": float(np.sum(after_win))}, Label.DERIVED, "Small sample; a pattern to monitor, not a finding."),
        "next_day_after_loss": m({"n": len(after_loss), "total": float(np.sum(after_loss))}, Label.DERIVED, "Small sample; a pattern to monitor, not a finding."),
        "hypothetical_caps": m(hypo, Label.HYPOTHETICAL),
        "intraday_sequence": m(None, Label.UNAVAILABLE, "Needs the F&O tradebook or contract notes; daily bills are one net figure per day."),
    }


def _money_section(ledger: pd.DataFrame) -> dict:
    dep = ledger[ledger["kind"] == LedgerKind.DEPOSIT.value]
    wd = ledger[ledger["kind"] == LedgerKind.WITHDRAWAL.value]
    loss_days = set(ledger.loc[(ledger["kind"] == LedgerKind.FNO_SETTLEMENT.value) & (ledger["amount"] < 0), "date"])
    after_loss = dep[dep["date"].map(lambda d: d in loss_days or (d - timedelta(days=1)) in loss_days)]
    last = ledger.iloc[-1]
    return {
        "period": m(f"{ledger['date'].min()} to {ledger['date'].max()}", Label.VERIFIED),
        "deposits_total": m(float(dep["amount"].sum()), Label.VERIFIED),
        "deposits_count": m(int(len(dep)), Label.VERIFIED),
        "withdrawals_total": m(float(-wd["amount"].sum()), Label.VERIFIED),
        "closing_balance": m(float(last["balance"]), Label.VERIFIED, f"as of {last['date']}"),
        "deposits_on_or_day_after_fno_loss": m({"count": int(len(after_loss)), "amount": float(after_loss["amount"].sum())}, Label.DERIVED,
                                               "A deposit on a loss day may have been made before the loss."),
        "pre_statement_capital": m(None, Label.UNAVAILABLE, "Deposits before the statement start date are not in this file."),
    }


def _stock_section(trades: pd.DataFrame, orders: pd.DataFrame, ledger: pd.DataFrame, seed: int) -> dict:
    if trades.empty:
        return {"available": False}
    s = summarize(trades["gross_pnl"].values, seed=seed)

    def bucket(days: int) -> str:
        return "same day" if days == 0 else ("1-7 days" if days <= 7 else "8+ days")

    by_hold = []
    for name in ["same day", "1-7 days", "8+ days"]:
        t = trades[trades["hold_days"].map(bucket) == name]
        if len(t):
            by_hold.append({"bucket": name, "trades": int(len(t)), "win_rate": float((t["gross_pnl"] > 0).mean()),
                            "gross_pnl": float(t["gross_pnl"].sum())})
    quick = trades[trades["hold_minutes"] <= 30]

    # Charges implied by the ledger: equity settlement cash minus order cash flows, per activity window,
    # restricted to dates the ledger covers. Window sums absorb the ledger posting a day late.
    start = ledger["date"].min()
    o = orders[orders["time"].dt.date >= start].copy()
    o["flow"] = np.where(o["side"] == "SELL", o["value"], -o["value"])
    eq = ledger[ledger["kind"] == LedgerKind.EQUITY_SETTLEMENT.value]
    recon, unsettled = [], []
    if not o.empty:
        for a, b in activity_windows(pd.concat([pd.Series(pd.to_datetime(o["time"].dt.date)), pd.Series(pd.to_datetime(eq["date"]))])):
            lo, hi = a, b + timedelta(days=3)
            flows = float(o.loc[(o["time"].dt.date >= lo) & (o["time"].dt.date <= b), "flow"].sum())
            bills = float(eq.loc[(eq["date"] >= lo) & (eq["date"] <= hi), "amount"].sum())
            turnover = float(o.loc[(o["time"].dt.date >= lo) & (o["time"].dt.date <= b), "value"].sum())
            if bills == 0 and flows != 0:  # orders not yet settled in this statement
                unsettled.append(f"{a} to {b}")
                continue
            recon.append({"from": str(a), "to": str(b), "order_cash_flow": round(flows, 2), "ledger_bills": round(bills, 2),
                          "implied_charges": round(flows - bills, 2), "turnover": round(turnover, 2),
                          "charges_pct_of_turnover": round((flows - bills) / turnover, 5) if turnover else None})
    charges_total = sum(r["implied_charges"] for r in recon)
    in_window = trades[trades["closed"].dt.date >= start]

    return {
        "available": True,
        "summary_gross": {k: m(v, Label.DERIVED) for k, v in s.as_dict().items()},
        "by_holding_period": m(by_hold, Label.DERIVED),
        "closed_within_30_min": m({"trades": int(len(quick)), "gross_pnl": float(quick["gross_pnl"].sum())}, Label.DERIVED),
        "largest_order_value": m(float(orders["value"].max()), Label.VERIFIED),
        "orders_count": m(int(len(orders)), Label.VERIFIED),
        "turnover": m(float(orders["value"].sum()), Label.VERIFIED),
        "charges_reconciliation": m(recon, Label.DERIVED,
                                    "Charges = order cash flows minus ledger equity bills over each window. Pre-statement buys carry no charge here."),
        "unsettled_windows": m(unsettled, Label.UNAVAILABLE, "Orders whose settlement is not in the statement yet."),
        "net_in_ledger_period": m({"gross_pnl": float(in_window["gross_pnl"].sum()), "implied_charges": float(charges_total),
                                   "net": float(in_window["gross_pnl"].sum() - charges_total)}, Label.DERIVED,
                                  "Trades closed on or after the ledger start; their pre-statement buy charges are missing, so net is slightly overstated."),
    }


def analyze(ledger: pd.DataFrame, orders: pd.DataFrame, trades: pd.DataFrame, seed: int = 7) -> dict:
    fno = _fno_section(ledger, seed)
    stocks = _stock_section(trades, orders, ledger, seed)
    verdict = []
    if fno.get("available"):
        ci = fno["summary"]["mean_ci95"]["value"]
        verdict.append({
            "segment": "F&O (options)",
            "edge_demonstrated": bool(ci[0] > 0),
            "reason": (f"Mean day {fno['summary']['mean']['value']:.0f} rupees, 95% interval "
                       f"{ci[0]:.0f} to {ci[1]:.0f}, over {fno['summary']['n']['value']} days. "
                       "An edge needs the whole interval above zero over a larger, rule-consistent sample."),
        })
    if stocks.get("available"):
        ci = stocks["summary_gross"]["mean_ci95"]["value"]
        verdict.append({
            "segment": "Stocks (cash)",
            "edge_demonstrated": bool(ci[0] > 0),
            "reason": (f"Mean trade {stocks['summary_gross']['mean']['value']:.1f} rupees before charges, 95% interval "
                       f"{ci[0]:.1f} to {ci[1]:.1f}, over {stocks['summary_gross']['n']['value']} trades; "
                       f"top trade is {stocks['summary_gross']['share_of_profit_from_top_result']['value']:.0%} of gross profit."),
        })
    return {"money": _money_section(ledger), "fno": fno, "stocks": stocks, "edge_verdict": verdict}
