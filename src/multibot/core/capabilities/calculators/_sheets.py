from __future__ import annotations
from typing import Optional

# _sheets.py — shared gspread helpers for all calculator load_items functions


def get_rows(ws) -> list:
    """Return all records with numericise disabled so decimal-comma values are preserved."""
    try:
        return ws.get_all_records(numericise_ignore=["all"])
    except TypeError:
        return ws.get_all_records()


def to_float(v) -> Optional[float]:
    """Parse a cell value to float, handling comma decimals and nbsp."""
    if v in ("", None):
        return None
    return float(str(v).replace("\xa0", "").replace(" ", "").replace(",", "."))
