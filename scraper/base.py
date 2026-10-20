from __future__ import annotations
import logging
import os
import time
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ScrapedRow(BaseModel):
    category: str
    item: str
    price: float
    price_unit: str = "грн"      # e.g. "грн/м²" or "грн/уп" or "грн"
    unit: str | None = None      # currency label (kept for compat)
    package_size: float | None = None
    package_unit: str | None = None
    volume_l: float | None = None      # volume in litres (л) if found on product page
    price_per_unit: float | None = None  # normalized price per 1 кг / 1 л / 1 м² for sorting
    source_name: str
    source_url: str
    collected_at: str
    attributes: dict = {}


@runtime_checkable
class SourceAdapter(Protocol):
    name: str
    base_url: str

    async def fetch(self, category: str) -> list[ScrapedRow]: ...


_SHEET_HEADER = [
    "category", "item", "price", "price_unit",
    "package_size", "package_unit", "volume_l",
    "source_name", "source_url", "collected_at",
    "active", "notes"
]


class SheetsWriter:
    """Upserts ScrapedRows into a Google Sheets worksheet.
    Key: category+item+source_name. Stale rows → active=false.
    """

    def __init__(self, creds_path: str, sheet_id: str):
        self._creds_path = creds_path
        self._sheet_id = sheet_id

    def _get_ws(self, worksheet_name: str):
        if not os.path.exists(self._creds_path):
            raise FileNotFoundError(f"Creds not found: {self._creds_path}")
        import gspread
        gc = gspread.service_account(filename=self._creds_path)
        spreadsheet = gc.open_by_key(self._sheet_id)
        try:
            return spreadsheet.worksheet(worksheet_name)
        except Exception:
            ws = spreadsheet.add_worksheet(title=worksheet_name, rows=2000, cols=len(_SHEET_HEADER))
            ws.append_row(_SHEET_HEADER)
            return ws

    def ensure_tab_exists(self, worksheet_name: str) -> None:
        """Create the tab with header if it doesn't exist yet."""
        try:
            self._get_ws(worksheet_name)
            logger.info(f"[sheets] Tab '{worksheet_name}' ready")
        except Exception as e:
            logger.warning(f"[sheets] Could not ensure tab '{worksheet_name}': {e}")

    def write_category_sheet(self, worksheet_name: str, header: list,
                              rows: list, row_builder) -> None:
        """
        Write a category-specific worksheet.
        - header: list of column names for this category
        - rows: list of ScrapedRow objects
        - row_builder: function(ScrapedRow) -> list of values matching header
        Rows are sorted by price_per_unit ascending (cheapest first).
        Items without price_per_unit go to the end.
        """
        # Sort: items with price_per_unit first (cheapest to most expensive),
        # then items where price_per_unit could not be calculated
        sorted_rows = sorted(
            rows,
            key=lambda r: (r.price_per_unit is None, r.price_per_unit or 0)
        )

        ws = self._get_ws_custom(worksheet_name, header)
        ws.clear()
        ws.append_row(header)
        if sorted_rows:
            values = [row_builder(r) for r in sorted_rows]
            ws.append_rows(values)
        logger.info(f"[scraper] Wrote '{worksheet_name}' with {len(sorted_rows)} rows sorted by price_per_unit")

    def _get_ws_custom(self, worksheet_name: str, header: list):
        """Get or create a worksheet with a custom header."""
        if not os.path.exists(self._creds_path):
            raise FileNotFoundError(f"Creds not found: {self._creds_path}")
        import gspread
        gc = gspread.service_account(filename=self._creds_path)
        spreadsheet = gc.open_by_key(self._sheet_id)
        try:
            return spreadsheet.worksheet(worksheet_name)
        except Exception:
            ws = spreadsheet.add_worksheet(title=worksheet_name, rows=2000, cols=len(header))
            return ws

    def recreate(self, worksheet_name: str, rows: list[ScrapedRow]) -> None:
        """Clear the worksheet and write all rows fresh."""
        ws = self._get_ws(worksheet_name)
        ws.clear()
        ws.append_row(_SHEET_HEADER)
        if rows:
            values = [
                [r.category, r.item, r.price, r.price_unit,
                 r.package_size or "", r.package_unit or "", r.volume_l or "",
                 r.source_name, r.source_url, r.collected_at, "true", ""]
                for r in rows
            ]
            ws.append_rows(values)
        logger.info(f"[scraper] Recreated '{worksheet_name}' with {len(rows)} rows")

    def upsert(self, worksheet_name: str, rows: list[ScrapedRow]) -> None:
        ws = self._get_ws(worksheet_name)
        all_records = ws.get_all_records()

        existing: dict[tuple, int] = {}
        for i, rec in enumerate(all_records, start=2):
            key = (str(rec.get("category", "")), str(rec.get("item", "")), str(rec.get("source_name", "")))
            existing[key] = i

        new_keys = {(r.category, r.item, r.source_name) for r in rows}

        for key, row_num in existing.items():
            if key not in new_keys:
                col_active = _SHEET_HEADER.index("active") + 1
                ws.update_cell(row_num, col_active, "false")

        for row in rows:
            key = (row.category, row.item, row.source_name)
            values = [
                row.category, row.item, row.price, row.price_unit,
                row.package_size or "", row.package_unit or "", row.volume_l or "",
                row.source_name, row.source_url, row.collected_at,
                "true", ""
            ]
            if key in existing:
                ws.update(f"A{existing[key]}", [values])
            else:
                ws.append_row(values)

        logger.info(f"[scraper] Upserted {len(rows)} rows into '{worksheet_name}'")
