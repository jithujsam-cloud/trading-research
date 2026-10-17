"""Probe what this account's Groww API plan actually returns.

Run on your own machine with credentials in the environment:
    tradelab audit-api --out reports/api_audit.json

Every probe is a read. Results record OK / FAILED and the error class only,
never response bodies with account details or credentials.
"""

import json
from datetime import date, timedelta
from pathlib import Path

from .readonly import ReadOnlyGroww, redact


def _probe(name: str, fn) -> dict:
    try:
        res = fn()
        size = len(res) if hasattr(res, "__len__") else None
        return {"probe": name, "status": "OK", "size": size}
    except Exception as e:  # record the failure class and a redacted message
        return {"probe": name, "status": "FAILED", "error": type(e).__name__, "message": redact(str(e))[:200]}


def run_audit(api: ReadOnlyGroww | None = None) -> list[dict]:
    api = api or ReadOnlyGroww()
    today = date.today()
    old_day = today - timedelta(days=400)
    probes = [
        ("profile", lambda: api.get_user_profile()),
        ("margin", lambda: api.get_available_margin_details()),
        # SDK 1.5.0 only sends `page` when `segment` is given, and never sends `page_size`
        ("orders_today_fno", lambda: api.get_order_list(page=0, segment="FNO")),
        ("orders_today_cash", lambda: api.get_order_list(page=0, segment="CASH")),
        ("positions", lambda: api.get_positions_for_user()),
        ("holdings", lambda: api.get_holdings_for_user()),
        ("ltp_nifty [paid?]", lambda: api.get_ltp(segment="CASH", exchange_trading_symbols=("NSE_NIFTY",))),
        ("expiries_nifty_this_year", lambda: api.get_expiries(exchange="NSE", underlying_symbol="NIFTY", year=today.year)),
        ("expiries_nifty_2020", lambda: api.get_expiries(exchange="NSE", underlying_symbol="NIFTY", year=2020)),
        ("candles_nifty_1min_recent [paid?]", lambda: api.get_historical_candles(
            exchange="NSE", segment="CASH", groww_symbol="NSE-NIFTY",
            start_time=f"{today - timedelta(days=5)} 09:15:00", end_time=f"{today - timedelta(days=1)} 15:30:00",
            candle_interval="1minute")),
        ("candles_nifty_1min_400_days_ago [lookback]", lambda: api.get_historical_candles(
            exchange="NSE", segment="CASH", groww_symbol="NSE-NIFTY",
            start_time=f"{old_day} 09:15:00", end_time=f"{old_day + timedelta(days=3)} 15:30:00",
            candle_interval="1minute")),
        ("candles_nifty_5min_2020 [lookback]", lambda: api.get_historical_candles(
            exchange="NSE", segment="CASH", groww_symbol="NSE-NIFTY",
            start_time="2020-03-02 09:15:00", end_time="2020-03-06 15:30:00", candle_interval="5minute")),
    ]
    results = [_probe(n, f) for n, f in probes]

    # expired option contract candles: pick a past expiry, list its contracts, fetch one
    def expired_option():
        exp = api.get_expiries(exchange="NSE", underlying_symbol="NIFTY", year=today.year - 1, month=6)
        expiries = exp.get("expiries", exp) if isinstance(exp, dict) else exp
        e = sorted(expiries)[-1]
        contracts = api.get_contracts(exchange="NSE", underlying_symbol="NIFTY", expiry_date=e)
        sym = (contracts.get("contracts", contracts) if isinstance(contracts, dict) else contracts)[0]
        return api.get_historical_candles(exchange="NSE", segment="FNO", groww_symbol=sym,
                                          start_time=f"{e} 09:15:00", end_time=f"{e} 15:30:00", candle_interval="5minute")
    results.append(_probe("expired_option_contract_5min [lookback]", expired_option))
    return results


def write_audit(path: str | Path, api: ReadOnlyGroww | None = None) -> list[dict]:
    results = run_audit(api)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps({"run_on": str(date.today()), "results": results}, indent=2))
    return results
