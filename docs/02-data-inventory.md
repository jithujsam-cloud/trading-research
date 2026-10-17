# Data inventory

## Have

| Dataset | Period | Label | Used for |
|---|---|---|---|
| Groww balance statement (ledger) | 1 Apr 2023 – 16 Oct 2026 | verified | Deposits, withdrawals, daily F&O net bills, equity bills |
| Groww stock order history | 11 Aug 2022 – 16 Oct 2026 | verified | Stock round trips (derived), turnover |
| Groww instrument file | 17 Oct 2026 | verified | Current Nifty lot size (65) |

## Missing, and exactly what to get

1. **F&O tradebook or contract notes** for 20 Sep – 22 Oct 2024 and 8 – 15 Oct 2026.
   - Contract notes are the legal record. Groww emails one after every trading day (PDF, usually password-protected with your PAN). Search your email for "contract note" from Groww for those dates.
   - Or, in the Groww app or website, open Reports and download the F&O trade history (tradebook) and the F&O P&L statement for those date ranges.
   - Without these, we cannot see contracts, lots, entry/exit times, intraday give-back, or actual charges.
2. **Ledger before 1 Apr 2023**, if you deposited money before then (FY 2022–23 balance statement).
3. **Market data for research** (needs one paid API month; download once and cache):
   - NIFTY 50 index, 1-minute and 5-minute candles, Jan 2020 – present.
   - NIFTY option contracts, 5-minute candles, for strikes within ±300 points of the index on each trading day, for the nearest weekly expiry. Contract list per expiry from `get_expiries` + `get_contracts`.
   - India VIX daily, if Groww serves it (to confirm), for regime and no-trade research.
4. **Lot size and expiry-day history** for NIFTY options from NSE circulars (lot size has changed several times since 2020, and the weekly expiry weekday has changed). Stored as an effective-dated table like `config/charges.yaml`.
5. **One recent contract note**, any trade, to check the charge rates marked `verify: true` in `config/charges.yaml`.

## Dependencies

- Python 3.10+, pandas, numpy, openpyxl, PyYAML (core).
- `growwapi` and `pyotp` for API access, in a separate virtualenv because `growwapi` pins `pandas<3`.
- A Groww API key created after you delete the one that was exposed in chat.
- A paid plan for one month when stage 3 starts.
