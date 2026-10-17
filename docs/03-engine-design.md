# Backtesting and paper-trading design

One codebase, two drivers. The same strategy code, execution model, cost model
and risk gate run in the backtest and in paper trading, so a difference between
them can only come from data or market conditions, not from two implementations.

```
 candles (cache) ─► BarFeed ─► Strategy.on_bar(bars_so_far) ─► Signal
                                                                  │
                         RiskGate (capital, 2% rule, daily limits, lot feasibility)
                                                                  │ accepted / rejected (both logged)
                                                                  ▼
                                       ExecutionModel (fills, slippage, gaps, missing data)
                                                                  │
                                       CostModel (effective-dated charges)
                                                                  ▼
                                       Ledger ─► Metrics + bootstrap ─► Report
```

## Components

- **Data cache.** Candles stored once per instrument and interval in SQLite/Parquet with `source`, `fetched_at` and a checksum. Validation flags gaps, duplicate or out-of-order bars, bars outside 09:15–15:30 IST, zero-volume bars, and expiry-day changes. Missing option bars are never forward-filled for fills.
- **BarFeed.** Yields one bar at a time in time order. A strategy receives a read-only view of bars up to and including the current close. There is no API to read a later bar, which prevents look-ahead by construction. A test feeds a series with a planted future spike and checks signals are unchanged when future bars are altered.
- **Strategy.** A pure function of past bars and its own state. Each spec has a version and a hash of its rules and parameters. Changing either creates a new version; results are stored per version.
- **RiskGate.** Independent of the strategy. Sizes the position from the stop and the per-trade limit, rejects a signal when one lot exceeds the limit (no rounding up, no switching to a cheaper strike), and applies daily loss, trade-count and cooldown rules. Every rejection is recorded with its reason.
- **ExecutionModel.**
  - Entry and exit at the **next bar's open** after a signal bar closes, never at the signal bar's close.
  - Spread and slippage: half-spread + slippage as a fraction of premium (default 0.5% + 0.5%, minimum 1 tick each side), stress-tested at 2× and 3×.
  - Stops: if a bar trades through the stop, fill at the worse of the stop price and the bar's open, minus slippage. If the option has no bar, the exit is delayed to the next available bar and flagged.
  - Lot sizes and expiries from the effective-dated table. Orders larger than the freeze quantity are rejected.
  - Expiry: positions are closed by 15:15 on expiry day in the base model.
- **CostModel.** `tradelab.costs`, effective-dated, calibrated against contract notes.
- **Metrics.** Net P&L after costs, trade count, win rate, average win and loss, expectancy with a bootstrap 95% interval, profit factor, max drawdown, results by year, by market regime (trend vs range from the index's 20-day behaviour, high vs low India VIX) and by entry hour, results with the best 5% of trades removed, and cost-sensitivity curves.
- **Baselines.**
  - No trade (₹0).
  - Benchmark: NIFTYBEES held over the same period, scaled to the same capital.
  - Random entry: same days and entry window, random time and direction, same exits, costs and sizing; 1,000 runs give a distribution the strategy is ranked against.

## Splits

Chronological, decided before any result is seen:

| Part | Period | Use |
|---|---|---|
| Development | Jan 2020 – Dec 2022 | Check the code does what the spec says. No parameter choice. |
| Validation | Jan 2023 – Dec 2024 | One run per spec version. |
| Final test | Jan 2025 – latest | Run once, after the spec and criteria are frozen. |

Parameters are fixed in the spec. A sensitivity grid is reported for robustness, never used to pick the best value.

## Paper trading

- Same Strategy, RiskGate, ExecutionModel and CostModel; the feed is live LTP and option-chain polling (paid plan), with candles built locally.
- A signal is logged even when rejected, with the reason. Fills are simulated with the backtest's execution model **and** with the actual quoted bid/ask at the time, so the two can be compared.
- The spec version is frozen for the whole evaluation. A change starts a new evaluation.
- Daily report: signals, simulated trades, P&L after costs, drawdown, and how each number compares with the backtest's distribution. A difference outside the backtest's 95% range is flagged.
- Stale data (last tick older than 60 s while the market is open) stops new signals and is recorded.
