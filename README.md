# tradelab

A personal research system for one question: **is there a trading strategy
with a real, after-cost edge that fits this account's capital?** If the
evidence says no, the system says no.

This code **cannot place, modify or cancel orders**. Broker access goes through
`ReadOnlyGroww`, which allows read methods only, and tests enforce that.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'

# your Groww exports go in data/raw/ (git-ignored)
tradelab history --ledger data/raw/ledger.xlsx --orders data/raw/stock_orders.xlsx
tradelab viability --instruments data/raw/instrument.csv    # current lot size from Groww's instrument file
pytest
```

Outputs go to `reports/` and `data/` (both git-ignored, because they contain
your financial records).

API audit (read-only; needs a fresh Groww API key in your environment, see
`.env.example`; `growwapi` needs its own virtualenv because it pins pandas < 3):

```bash
pip install growwapi pyotp
tradelab audit-api
```

## Web app (Vercel)

A password-protected, read-only web app: upload statements, see the report and
the option-viability table, and save a daily snapshot of today's orders and
fills (Groww's API keeps only today's). Setup: `docs/07-deploy-vercel.md`.
Run it locally with:

```bash
APP_PASSWORD=pick-one SESSION_SECRET=$(python -c "import secrets;print(secrets.token_hex(32))") \
  uvicorn tradelab.web.app:app --app-dir src --reload
```

## How numbers are labelled

| Label | Meaning |
|---|---|
| verified | Copied from a broker record |
| derived | Calculated only from broker records (e.g. FIFO round trips) |
| estimated | Depends on a model, such as the charge schedule |
| hypothetical | A what-if that did not happen. Never evidence of an edge |
| unavailable | The data needed is missing |

## Layout

```
src/tradelab/
  ingest/        Groww ledger and order-history importers with validation
  reconstruct.py FIFO round trips
  costs.py       effective-dated charge model (config/charges.yaml)
  stats.py       expectancy, drawdown, profit factor, bootstrap intervals
  history.py     analysis of past results
  viability.py   can one option lot fit the risk limit?
  broker/        read-only Groww wrapper, credential redaction, API audit
  store.py       clean dataset (SQLite + CSV) with provenance
  web/           FastAPI app, login, Supabase storage, daily snapshot job
api/index.py     Vercel entry point
supabase/        database migration
docs/            audit, data inventory, engine design, Strategy A spec, go-live criteria, plan
```

## Known limitations

- F&O results come from one net settlement figure per day. Without contract notes, contracts, entry/exit times, intraday give-back and actual charges are unavailable.
- Stock round trips have no fill-level detail; profits are before charges. Charges are inferred per activity window from the ledger.
- Charge rates marked `verify: true` in `config/charges.yaml` came from secondary sources.
- The ledger starts on 1 Apr 2023; earlier deposits are unknown.
- No backtest exists yet. Nothing here shows that any strategy works.
