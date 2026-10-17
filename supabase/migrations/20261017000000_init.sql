-- tradelab storage. Row-level security is on with no policies, so only the
-- service-role key (used server-side by the Vercel app) can read or write.

create table if not exists broker_orders (
  groww_order_id text primary key,
  segment        text not null,
  trade_date     date not null,
  status         text,
  payload        jsonb not null,
  first_seen_at  timestamptz not null default now(),
  last_seen_at   timestamptz not null default now()
);

create table if not exists broker_fills (
  fill_id        text primary key,
  groww_order_id text not null references broker_orders (groww_order_id),
  segment        text not null,
  payload        jsonb not null,
  fetched_at     timestamptz not null default now()
);

create table if not exists broker_snapshots (
  id        bigint generated always as identity primary key,
  kind      text not null check (kind in ('positions', 'margin', 'holdings')),
  taken_at  timestamptz not null default now(),
  payload   jsonb not null
);

create table if not exists snapshot_runs (
  id          bigint generated always as identity primary key,
  started_at  timestamptz not null default now(),
  finished_at timestamptz,
  status      text not null check (status in ('ok', 'partial', 'failed')),
  details     jsonb
);

create table if not exists history_reports (
  id          bigint generated always as identity primary key,
  created_at  timestamptz not null default now(),
  report      jsonb not null
);

create table if not exists settings (
  key         text primary key,
  value       jsonb not null,
  updated_at  timestamptz not null default now()
);

create index if not exists broker_orders_trade_date on broker_orders (trade_date);
create index if not exists broker_fills_order on broker_fills (groww_order_id);
create index if not exists broker_snapshots_kind_time on broker_snapshots (kind, taken_at desc);
create index if not exists snapshot_runs_time on snapshot_runs (started_at desc);
create index if not exists history_reports_time on history_reports (created_at desc);

alter table broker_orders    enable row level security;
alter table broker_fills     enable row level security;
alter table broker_snapshots enable row level security;
alter table snapshot_runs    enable row level security;
alter table history_reports  enable row level security;
alter table settings         enable row level security;
