# Running tradelab on Vercel

The web app is read-only: it analyses uploaded Groww statements, shows the
option-viability table, and saves a daily snapshot of today's orders, fills,
positions and funds. It cannot place, modify or cancel orders.

## 1. Database (Supabase)

1. Create a Supabase project (or use an existing one).
2. Run `supabase/migrations/20261017000000_init.sql` in the SQL editor. It creates the tables with row-level security on and no policies, so the public anon key cannot read them.
3. Copy the project URL and the **service-role** key (Settings → API). The service-role key is used only on the server and must never be put in browser code.

Without a database the app still works, but reports are not saved and snapshots are off.

## 2. Vercel project

1. Import `jithujsam-cloud/trading-research` in Vercel. Framework preset: Other. No build command.
2. Add environment variables (Settings → Environment Variables, Production):

| Name | Value |
|---|---|
| `APP_PASSWORD` | A long password you choose for logging in |
| `SESSION_SECRET` | A random string of at least 32 characters (e.g. `python -c "import secrets; print(secrets.token_hex(32))"`) |
| `CRON_SECRET` | Another random string; Vercel sends it to the snapshot job |
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | The service-role key |
| `GROWW_API_KEY` | A **new** Groww API key (delete the one shared in chat first) |
| `GROWW_TOTP_SECRET` | The TOTP secret for that key (or `GROWW_API_SECRET` for the approval method) |

3. Deploy. Open `/health`: it reports which settings are present (true/false only).

## 3. Daily snapshot

`vercel.json` schedules `/api/cron/snapshot` at 10:45 UTC (16:15 IST), Monday to
Friday. On the Hobby plan Vercel may run it any time within that hour. Check
the **Daily snapshots** page the next evening.

## What is stored

| Table | Contents |
|---|---|
| `broker_orders`, `broker_fills` | Each day's orders and fills as Groww returned them |
| `broker_snapshots` | Positions and funds at snapshot time |
| `snapshot_runs` | When each snapshot ran and what failed |
| `history_reports` | The analysis of each statement upload (the uploaded files are not stored) |
| `settings` | The current Nifty lot size from Groww's instrument file |

## Automatic deploys

Vercel deploys every push to `main`. On the Hobby plan it skips a commit whose
author is not the Vercel account owner, so commits in this repository are
authored as the owner. If a push does not deploy, open Deployments in Vercel
and check for a "blocked" notice, or use Redeploy on the latest deployment.

## Limits

- The Groww key lives in Vercel's encrypted settings. It can read your account and, through Groww directly, could place orders, so treat it like a password. This app never uses it for orders.
- The research commands (backtests, data downloads) run on your own computer, not on Vercel: they take longer than a Vercel request allows.
- Upload size is limited to 4 MB per file.
