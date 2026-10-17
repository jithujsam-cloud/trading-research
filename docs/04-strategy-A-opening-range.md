# Strategy A v1: Nifty opening-range breakout (pre-registered)

Status: specified, not tested. Rules and parameters below are fixed before any
data is examined. Any change creates version 2 and restarts testing.

## Why test this first

- It is the closest rule-based version of what you were doing: intraday Nifty option buying.
- It makes at most one trade a day, which directly limits overtrading.
- Every input (index candles, option candles, expiries, lot size) is available from the Groww backtesting API from 2020.
- A clean "no" is useful too. If the simplest disciplined version of your style fails after costs, intraday option buying should stay off with real money.

## Data

- Signal: NIFTY 50 index (`NSE-NIFTY`), 5-minute candles, IST.
- Execution: NIFTY option contract 5-minute candles for the chosen strike and expiry.

## Rules

1. **Opening range.** High `H` and low `L` of the three 5-minute candles from 09:15 to 09:30. `R = H − L`.
2. **Signal window.** Candles closing from 09:35 to 11:00 inclusive.
3. **Signal.** The first candle in the window that closes above `H` gives a long signal (buy a call). The first that closes below `L` gives a short signal (buy a put). Only the first signal of the day counts.
4. **Contract.** Nearest weekly expiry that is not today. Strike: the index close at the signal candle rounded to the nearest 50 (at the money).
5. **Entry.** Open of the next 5-minute candle of that option, plus half-spread and slippage.
6. **Exits**, whichever comes first:
   - a. Invalidation: an index candle closes back beyond the range midpoint `(H + L) / 2` → exit at the next option candle's open.
   - b. Premium stop: option price trades 35% below entry → fill at the worse of the stop and the candle's open, minus slippage.
   - c. Target: index trades `1.5 × R` beyond the breakout level (`H` or `L`) → exit at the next option candle's open.
   - d. Time: exit at the open of the 15:00 candle.
7. **Size.** `lots = floor(0.02 × capital / risk_per_lot)`, where `risk_per_lot` = 35% of entry premium × lot size + stop slippage + estimated round-trip charges. If `lots < 1`, the signal is **rejected** and logged; no smaller or cheaper contract is substituted.
8. **No trade** if a candle is missing for the index or option at entry, or if the option's previous candle had zero volume.

## Parameters (fixed)

Opening range 15 min · signal window to 11:00 · stop 35% · target 1.5R · time exit 15:00 · risk 2% · nearest non-expiring weekly expiry · ATM strike.

## Reported in addition

- A sensitivity grid (opening range 15/30 min, stop 25/35/50%, target 1R/1.5R/2R) to show robustness only.
- The share of signals rejected because one lot exceeds 2% of capital, at ₹2,000, ₹16,000 and ₹1,00,000. If almost all are rejected at your capital, the strategy is not usable by you even if it works.

## Strategy B and C (later)

- **B, trend pullback:** specified after A's validation run, so it is not designed around A's results.
- **C, no-trade filter:** tested only as a filter on A (for example skip expiry days, opening gaps above 1%, opening ranges above the 90th percentile). Each filter is pre-registered and judged on the validation period only.
- **Cash-market alternative:** a daily-candle swing study on Nifty 50 stocks and ETFs, using the same engine and criteria. This one fits small capital, because single shares can be sized to 2% risk.
