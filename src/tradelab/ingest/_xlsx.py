"""Shared helpers for Groww's xlsx exports, which put metadata rows above the table."""

from pathlib import Path

import openpyxl


def read_table(path: str | Path, header_first_cell: str) -> tuple[list[str], list[tuple]]:
    """Return (header, rows) for the first table whose header starts with `header_first_cell`.

    Rows stop at the first fully blank row after the header. Personal metadata above
    the header (name, PAN, client codes) is never returned.
    """
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb.worksheets[0]
        header: list[str] | None = None
        rows: list[tuple] = []
        for raw in ws.iter_rows(values_only=True):
            if header is None:
                if raw and isinstance(raw[0], str) and raw[0].strip() == header_first_cell:
                    header = [str(c).strip() if c is not None else "" for c in raw]
                continue
            if raw is None or all(c is None or (isinstance(c, str) and not c.strip()) for c in raw):
                break
            rows.append(tuple(raw[: len(header)]))
        if header is None:
            raise ValueError(f"{Path(path).name}: no table starting with {header_first_cell!r}")
        return header, rows
    finally:
        wb.close()
