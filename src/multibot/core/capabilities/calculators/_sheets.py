# _sheets.py — shared gspread helpers for all calculator load_items functions


def get_rows(ws) -> list[dict]:
    """Return all records with numericise disabled so decimal-comma values are preserved."""
    try:
        return ws.get_all_records(numericise_ignore=["all"])
    except TypeError:
        # older gspread that doesn't support numericise_ignore
        return ws.get_all_records()


def to_float(v) -> float | None:
    """Parse a cell value to float, handling comma decimals and nbsp."""
    if v in ("", None):
        return None
    return float(str(v).replace("\xa0", "").replace(" ", "").replace(",", "."))
