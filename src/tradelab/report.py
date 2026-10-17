"""Render the history analysis and viability grid as Markdown and JSON."""

import json
from pathlib import Path


def rs(v) -> str:
    if v is None:
        return "n/a"
    sign = "−" if v < 0 else ""
    return f"{sign}₹{abs(v):,.0f}"


def rs1(v) -> str:
    return f"{'−' if v < 0 else ''}₹{abs(v):,.1f}"


def pct(v) -> str:
    return "n/a" if v is None else f"{v:.0%}"


def _v(metric: dict):
    return metric["value"]


def _tag(metric: dict) -> str:
    return f"[{metric['label']}]"


def history_markdown(a: dict, validation: list[str]) -> str:
    L: list[str] = []
    w = L.append
    w("# Trading history analysis\n")
    w("Labels: **verified** = broker record · **derived** = computed only from broker records · "
      "**estimated** = depends on a cost model · **hypothetical** = did not happen · **unavailable** = data missing.\n")

    w("## Data validation\n")
    for msg in validation or ["No validation issues."]:
        w(f"- {msg}")
    w("")

    mo = a["money"]
    w("## Money in and out\n")
    w(f"- Period: {_v(mo['period'])} {_tag(mo['period'])}")
    w(f"- Deposited: {rs(_v(mo['deposits_total']))} in {_v(mo['deposits_count'])} deposits {_tag(mo['deposits_total'])}")
    w(f"- Withdrawn: {rs(_v(mo['withdrawals_total']))} {_tag(mo['withdrawals_total'])}")
    w(f"- Closing balance: {rs(_v(mo['closing_balance']))} ({mo['closing_balance']['note']}) {_tag(mo['closing_balance'])}")
    d = _v(mo["deposits_on_or_day_after_fno_loss"])
    w(f"- Deposits on a losing F&O day or the day after: {d['count']} worth {rs(d['amount'])} {_tag(mo['deposits_on_or_day_after_fno_loss'])}")
    w(f"- Money deposited before the statement: unavailable — {mo['pre_statement_capital']['note']}\n")

    f = a["fno"]
    if f.get("available"):
        s = {k: _v(v) for k, v in f["summary"].items()}
        w("## F&O (from daily settlement bills)\n")
        w("Each figure below is one net amount per day, including charges. Contract, lot and intraday details are unavailable.\n")
        w("| Measure | Value |\n|---|---|")
        w(f"| Days traded | {s['n']} |")
        w(f"| Net result | {rs(s['total'])} |")
        w(f"| Winning days | {pct(s['win_rate'])} |")
        w(f"| Average winning day / losing day | {rs(s['avg_win'])} / {rs(-s['avg_loss'])} |")
        w(f"| Win rate needed to break even at those sizes | {pct(s['breakeven_win_rate'])} |")
        w(f"| Mean day (95% interval) | {rs(s['mean'])} ({rs(s['mean_ci95'][0])} to {rs(s['mean_ci95'][1])}) |")
        w(f"| Share of bootstrap samples with a positive mean | {pct(s['prob_mean_positive'])} |")
        w(f"| Profit factor | {s['profit_factor']:.2f} |")
        w(f"| Largest drawdown | {rs(-s['max_drawdown'])} |")
        w(f"| Days at +₹500 or better / −₹500 or worse | {_v(f['days_at_or_above_500'])} / {_v(f['days_at_or_below_minus_500'])} |")
        w(f"| Worst losing day as share of cash available that day | {pct(_v(f['worst_loss_pct_of_balance']))} |")
        w(f"| Median losing day as share of cash available | {pct(_v(f['median_loss_pct_of_balance']))} |")
        w("")
        w("All rows [derived] from [verified] daily bills.\n")
        w("**Episodes**\n")
        w("| From | To | Days | Result |\n|---|---|---|---|")
        for e in f["episodes"]:
            w(f"| {e['from']} | {e['to']} | {e['days']} | {rs(e['result'])} |")
        w("")
        aw, al = _v(f["next_day_after_win"]), _v(f["next_day_after_loss"])
        w(f"**Day after a win vs after a loss** [derived, small sample]: after {aw['n']} winning days the next day totalled "
          f"{rs(aw['total'])}; after {al['n']} losing days, {rs(al['total'])}.\n")
        h = _v(f["hypothetical_caps"])
        w("**What-if daily caps** [hypothetical — not evidence]\n")
        w(f"_{h['assumption']}_\n")
        w("| Rule | Result |\n|---|---|")
        for k, label in [("actual", "What happened"), ("stop_after_plus_500", "Stop after +₹500"),
                         ("stop_at_minus_1000", "Stop at −₹1,000"), ("stop_at_minus_500", "Stop at −₹500"),
                         ("stop_at_both_500", "Stop at ±₹500"),
                         ("stop_at_minus_500_without_best_2_days", "Stop at −₹500, best 2 days removed")]:
            w(f"| {label} | {rs(h[k])} |")
        w(f"\nIntraday profit give-back: unavailable — {f['intraday_sequence']['note']}\n")

    st = a["stocks"]
    if st.get("available"):
        s = {k: _v(v) for k, v in st["summary_gross"].items()}
        w("## Stocks (FIFO round trips, before charges)\n")
        w("| Measure | Value |\n|---|---|")
        w(f"| Closed trades | {s['n']} |")
        w(f"| Gross result | {rs(s['total'])} |")
        w(f"| Win rate | {pct(s['win_rate'])} |")
        w(f"| Mean trade (95% interval) | {rs1(s['mean'])} ({rs1(s['mean_ci95'][0])} to {rs1(s['mean_ci95'][1])}) |")
        w(f"| Largest trade's share of gross profit | {pct(s['share_of_profit_from_top_result'])} |")
        w(f"| Result without the best 3 trades | {rs(s['total_without_top_3'])} |")
        w(f"| Orders / turnover | {_v(st['orders_count'])} / {rs(_v(st['turnover']))} |")
        w(f"| Largest single order | {rs(_v(st['largest_order_value']))} |")
        q = _v(st["closed_within_30_min"])
        w(f"| Trades closed within 30 minutes | {q['trades']} trades, {rs(q['gross_pnl'])} |")
        w("")
        w("**By holding period** [derived]\n")
        w("| Held | Trades | Won | Gross |\n|---|---|---|---|")
        for b in _v(st["by_holding_period"]):
            w(f"| {b['bucket']} | {b['trades']} | {pct(b['win_rate'])} | {rs(b['gross_pnl'])} |")
        w("")
        w("**Charges implied by the ledger** [derived]\n")
        w("| Window | Turnover | Implied charges | Share of turnover |\n|---|---|---|---|")
        for r in _v(st["charges_reconciliation"]):
            w(f"| {r['from']} to {r['to']} | {rs(r['turnover'])} | {rs(r['implied_charges'])} | "
              f"{'n/a' if r['charges_pct_of_turnover'] is None else f'{r['charges_pct_of_turnover']:.2%}'} |")
        for u in _v(st["unsettled_windows"]):
            w(f"\nNot yet settled in the statement, so excluded: {u}.")
        n = _v(st["net_in_ledger_period"])
        w(f"\nTrades closed inside the statement period: gross {rs(n['gross_pnl'])}, implied charges {rs(n['implied_charges'])}, "
          f"net about {rs(n['net'])}. {st['net_in_ledger_period']['note']}\n")

    w("## Is there an edge?\n")
    for v in a["edge_verdict"]:
        w(f"- **{v['segment']}: {'edge shown' if v['edge_demonstrated'] else 'no edge demonstrated'}.** {v['reason']}")
    w("")
    return "\n".join(L)


def viability_markdown(rows: list[dict], lot_size: int, lot_source: str, on: str, risk_limit: float) -> str:
    L = ["# Nifty option buying: does one lot fit the risk limit?\n",
         f"Lot size {lot_size} ({lot_source}). Charges estimated with rates in force on {on}. "
         f"Risk limit {risk_limit:.0%} of capital per trade. Stop slippage: 5% of premium, at least 2 ticks.\n",
         "Total risk = premium lost to the stop + slippage past the stop + estimated round-trip charges, for ONE lot (the minimum).\n"]
    capitals = sorted({r["capital"] for r in rows})
    for c in capitals:
        L.append(f"## Capital {rs(c)} — limit {rs(c * risk_limit)} per trade\n")
        L.append("| Premium | Stop | One lot costs | Total risk | % of capital | Affordable | Within limit | Capital needed for limit |")
        L.append("|---|---|---|---|---|---|---|---|")
        for r in rows:
            if r["capital"] != c:
                continue
            L.append(f"| ₹{r['premium']:g} | {r['stop_pct']:.0%} | {rs(r['lot_cost'])} | {rs(r['total_risk'])} | "
                     f"{r['risk_pct_of_capital']:.1%} | {'yes' if r['affordable'] else 'no'} | "
                     f"{'yes' if r['within_limit'] else '**no**'} | {rs(r['min_capital_for_limit'])} |")
        L.append("")
    return "\n".join(L)


def write(path: str | Path, text: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text)


def write_json(path: str | Path, obj) -> None:
    write(path, json.dumps(obj, indent=2, default=str, ensure_ascii=False))
