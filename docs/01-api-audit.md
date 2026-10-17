# Groww API audit

Checked on 17 Oct 2026 against Groww's published docs and the source of the
official Python SDK (`growwapi` 1.5.0, released 3 Dec 2025). Items marked
**to confirm** are settled by running `tradelab audit-api` on your machine.

## What exists

| Need | SDK method(s) | Plan | Notes |
|---|---|---|---|
| Login | `GrowwAPI.get_access_token(api_key, totp=…)` or `(api_key, secret=…)` | any | TOTP keys do not expire until revoked. Token endpoint limited to 150 calls/day. |
| Today's orders | `get_order_list`, `get_order_detail`, `get_order_status` | free | Docs describe the list as the day's orders. **There is no order or trade history endpoint for past days.** |
| Fills for an order | `get_trade_list_for_order` | free | Fill prices and quantities; use for partial fills. |
| Positions | `get_positions_for_user`, `get_position_for_trading_symbol` | free | Returns `realised_pnl` only. Unrealised P&L must be computed from live prices. |
| Holdings | `get_holdings_for_user` | free | Quantity and average price; no P&L. |
| Funds and margin | `get_available_margin_details` | free | Cash and margin by segment. |
| Charges for a planned order | `get_order_margin_details` | free | Response includes `brokerage_and_charges`. Best source for pre-trade cost. |
| Live price, quote, OHLC | `get_ltp`, `get_quote`, `get_ohlc` | **paid** | Up to 50 instruments per LTP/OHLC call. |
| Option chain with Greeks | `get_option_chain`, `get_greeks` | **paid** | Per underlying and expiry. |
| Historical candles | `get_historical_candles` (new), `get_historical_candle_data` (deprecated) | **paid** | Backtesting docs: equities, indices and F&O from 2020; 1–5 min candles in 30-day requests. The older historical-data page says minute data covers only the last 3 months. **To confirm.** |
| Expired option contracts | `get_expiries`, `get_contracts` + candles | **paid** | Documented example uses a past Nifty contract symbol. **To confirm** how far back. |
| Instruments and lot sizes | `get_all_instruments` (public CSV) | none | Read on 17 Oct 2026: every NIFTY option has lot size **65**; 18 expiries listed. Only current contracts. |
| Streaming | `GrowwFeed` (LTP, depth, index, order and position updates) | paid for prices | Usable later to detect trades immediately. |
| Place, modify, cancel; GTT and OCO | `place_order`, `modify_order`, `cancel_order`, `*_smart_order` | free | **Blocked in this project** by `ReadOnlyGroww`. |

Rate limits (docs): orders 10/s, 250/min; live data 10/s, 300/min; other reads 20/s, 500/min.
Pricing (Groww blog): free trial excludes live data and backtesting; ₹499/month or ₹4,999/year plus GST.

## What does not exist

- **Past orders, trades or P&L.** History must come from Groww's statement exports and contract notes. From now on the system must save each day's orders and fills itself.
- **Deposits, withdrawals, ledger.** Statement export only.
- **Historical bid/ask.** Candles are traded prices; spreads must be modelled and stress-tested.
- **Historical lot sizes.** The instrument file has today's contracts only; past lot sizes come from NSE circulars.
- **A kill switch or account-level trading block.** Not in the API or SDK. Software cannot stop an order placed in the Groww app.

## Problems found in the SDK

- `get_order_list` sends `page` only when `segment` is given and never sends `page_size`. Always pass `segment`, and page until a short page is returned.
- `growwapi` requires `pandas<3`. Install it in its own virtualenv.
- `GrowwAPI.__init__` downloads the full instrument CSV (about 20 MB) on every start. Cache it.

## Not settled by the docs

- Whether Groww requires registration, a static IP or an algo ID for orders placed through the API under SEBI's 2025 retail algo framework. This matters only if live orders are ever enabled; confirm with Groww first.

## How this project uses the API

- `tradelab.broker.ReadOnlyGroww` allows only the read methods listed in `READ_METHODS`. Write methods raise `ReadOnlyViolation`. Tests enforce this.
- Credentials are read from environment variables only. Error messages pass through `redact()`; nothing is written to logs or reports.
- `tradelab audit-api` makes read-only probes and records only OK/FAILED and the error class.
