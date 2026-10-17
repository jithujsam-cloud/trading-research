# Implementation plan

Research comes before the dashboard. Each stage ends with tests and a written
note of what it can and cannot show.

| Stage | Builds | Status | Needs |
|---|---|---|---|
| **1. Research foundation** | Importers for the Groww ledger and stock orders with validation; clean dataset (SQLite + CSV) with provenance; FIFO round trips; effective-dated cost model; statistics with bootstrap intervals; history report; option lot-viability calculator; read-only API wrapper and audit command; pre-registered Strategy A and go-live criteria | **Done** | — |
| **1b. Web app on Vercel** | Login, statement upload and report, option viability, read-only daily snapshot of orders, fills, positions and funds into Supabase | **Done** | Vercel + Supabase settings |
| **2. Fill the gaps** | Run `audit-api`; parse F&O contract notes and tradebook; calibrate `charges.yaml` against actual charges; answer the give-back and repeat-entry questions from real F&O trades | Next | Your contract notes or tradebook, a new API key |
| **3. Market data layer** | Candle downloader with chunking, rate limiting, caching and validation; expiry and contract lists; lot-size history | | One paid API month |
| **4. Backtest engine + Strategy A** | Components in `03-engine-design.md`; look-ahead tests; baselines; development run, then one validation run, then one final run | | Stage 3 data |
| **5. Other hypotheses** | Strategy B spec and test; Strategy C filters on A; cash-market swing study | | Stage 4 |
| **6. Risk engine + journal** | ACTIVE / CAUTION / LOCKED states; daily loss and trade limits; consecutive losses; size-increase-after-loss and no-exit detection; trades with no plan; daily read-only snapshots of orders and fills (the API keeps only today's); end-of-session report; phone alerts | | Free API plan |
| **7. Paper trading** | Live driver for the same engine; signal log including rejections; comparison with backtest | | Paid plan, a strategy that passed stage 4 |
| **8. Go-live review** | Check `05-go-live-criteria.md`. Live execution code is not written unless it passes. | | All of the above |

## What protects you before stage 6

The software cannot block the Groww app. Until the risk engine exists, the
strongest safeguard is outside the software: keep only the money you are
prepared to lose this week in Groww and the rest in your bank, so Groww's own
margin check enforces your limit.
