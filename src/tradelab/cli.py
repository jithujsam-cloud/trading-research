"""Command line entry point.

    tradelab history   --ledger data/raw/ledger.xlsx --orders data/raw/stock_orders.xlsx
    tradelab viability --capital 2000 4000 16000 [--instruments data/raw/instrument.csv]
    tradelab audit-api (needs Groww credentials in the environment; read-only)
"""

import argparse
import sys
from datetime import date
from pathlib import Path

from . import report
from .costs import CostModel
from .pipeline import run_history
from .store import write_clean_dataset
from .viability import grid

DEFAULT_LOT_SIZE = 65  # NIFTY, Groww instrument file 17 Oct 2026; re-read with --instruments


def cmd_history(args) -> int:
    result, tables = run_history(args.ledger, args.orders, seed=args.seed)
    write_clean_dataset(Path(args.data) / "tradelab.db", Path(args.data) / "clean", tables)
    report.write_json(Path(args.out) / "history.json", result)
    report.write(Path(args.out) / "history.md", report.history_markdown(result, result["validation"]))
    print(f"wrote {Path(args.out) / 'history.md'} and {Path(args.data) / 'tradelab.db'}")
    return 0


def lot_size_from_instruments(path: str, underlying: str = "NIFTY") -> int:
    import pandas as pd
    d = pd.read_csv(path, low_memory=False, usecols=["underlying_symbol", "instrument_type", "lot_size"])
    sizes = d[(d["underlying_symbol"] == underlying) & d["instrument_type"].isin(["CE", "PE"])]["lot_size"].dropna().unique()
    if len(sizes) != 1:
        raise ValueError(f"expected one {underlying} option lot size, found {sorted(sizes)}")
    return int(sizes[0])


def cmd_viability(args) -> int:
    if args.instruments:
        lot, source = lot_size_from_instruments(args.instruments), f"read from {Path(args.instruments).name}"
    else:
        lot, source = DEFAULT_LOT_SIZE, "default; pass --instruments to read the current value"
    on = args.on or str(date.today())
    rows = [r.as_dict() for r in grid(args.capital, args.premium, args.stop, lot, on, CostModel(), args.risk_limit)]
    report.write_json(Path(args.out) / "viability.json", {"lot_size": lot, "lot_source": source, "on": on, "rows": rows})
    report.write(Path(args.out) / "viability.md", report.viability_markdown(rows, lot, source, on, args.risk_limit))
    print(f"wrote {Path(args.out) / 'viability.md'}")
    return 0


def cmd_audit(args) -> int:
    from .broker.audit import write_audit
    results = write_audit(Path(args.out) / "api_audit.json")
    for r in results:
        print(f"{r['status']:7} {r['probe']}" + (f"  ({r.get('error')})" if r["status"] != "OK" else ""))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="tradelab")
    sub = p.add_subparsers(dest="cmd", required=True)

    h = sub.add_parser("history", help="import Groww exports and analyse past results")
    h.add_argument("--ledger", required=True)
    h.add_argument("--orders", required=True)
    h.add_argument("--data", default="data")
    h.add_argument("--out", default="reports")
    h.add_argument("--seed", type=int, default=7)
    h.set_defaults(fn=cmd_history)

    v = sub.add_parser("viability", help="can one option lot fit the per-trade risk limit?")
    v.add_argument("--capital", type=float, nargs="+", default=[2000, 4000, 16000])
    v.add_argument("--premium", type=float, nargs="+", default=[10, 20, 50, 100, 150])
    v.add_argument("--stop", type=float, nargs="+", default=[0.2, 0.35])
    v.add_argument("--risk-limit", type=float, default=0.02)
    v.add_argument("--instruments", help="Groww instrument.csv to read the current lot size from")
    v.add_argument("--on", help="date for the charge schedule (YYYY-MM-DD); default today")
    v.add_argument("--out", default="reports")
    v.set_defaults(fn=cmd_viability)

    a = sub.add_parser("audit-api", help="probe the Groww API with read-only calls")
    a.add_argument("--out", default="reports")
    a.set_defaults(fn=cmd_audit)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
