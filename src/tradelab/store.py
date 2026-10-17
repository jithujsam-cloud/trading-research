"""Clean dataset on disk: one SQLite file plus CSV copies, every table with provenance.

The database lives under data/ (git-ignored). Tables are rebuilt from the raw
exports on every import, so the raw files remain the single source of truth.
"""

import sqlite3
from pathlib import Path

import pandas as pd

from .provenance import Label

TABLE_LABELS = {
    "ledger": (Label.VERIFIED, "Groww balance statement; order within a day repaired only where the running balance proves it"),
    "stock_orders": (Label.VERIFIED, "Groww stock order history, executed orders only"),
    "stock_round_trips": (Label.DERIVED, "FIFO matching of executed orders; gross of charges"),
    "stock_open_lots": (Label.DERIVED, "Unmatched quantity left after FIFO matching"),
}


def write_clean_dataset(db_path: str | Path, csv_dir: str | Path, tables: dict[str, pd.DataFrame]) -> None:
    db_path, csv_dir = Path(db_path), Path(csv_dir)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    csv_dir.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as con:
        con.execute("DROP TABLE IF EXISTS provenance")
        con.execute("CREATE TABLE provenance (table_name TEXT PRIMARY KEY, label TEXT, source TEXT, rows INTEGER)")
        for name, df in tables.items():
            df.to_sql(name, con, if_exists="replace", index=False)
            label, source = TABLE_LABELS.get(name, (Label.ESTIMATED, "unknown"))
            con.execute("INSERT INTO provenance VALUES (?, ?, ?, ?)", (name, label.value, source, len(df)))
            df.to_csv(csv_dir / f"{name}.csv", index=False)
