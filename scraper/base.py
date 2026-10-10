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
    unit: str | None = None
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
    "category", "item", "price", "unit",
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

    def recreate(self, worksheet_name: str, rows: list[ScrapedRow]) -> None:
        """Clear the worksheet and write all rows fresh."""
        ws = self._get_ws(worksheet_name)
        ws.clear()
        ws.append_row(_SHEET_HEADER)
        if rows:
            values = [
                [r.category, r.item, r.price, r.unit or "",
                 r.source_name, r.source_url, r.collected_at, "true", ""]
                for r in rows
            ]
            ws.append_rows(values)
        logger.info(f"[scraper] Recreated '{worksheet_name}' with {len(rows)} rows")

    def upsert(self, worksheet_name: str, rows: list[ScrapedRow]) -> None:
        ws = self._get_ws(worksheet_name)
        all_records = ws.get_all_records()

        # Build index: (category, item, source_name) → row_number (1-based, +1 for header)
        existing: dict[tuple, int] = {}
        for i, rec in enumerate(all_records, start=2):
            key = (str(rec.get("category", "")), str(rec.get("item", "")), str(rec.get("source_name", "")))
            existing[key] = i

        new_keys = {(r.category, r.item, r.source_name) for r in rows}

        # Mark stale rows as inactive
        for key, row_num in existing.items():
            if key not in new_keys:
                col_active = _SHEET_HEADER.index("active") + 1
                ws.update_cell(row_num, col_active, "false")

        # Upsert new rows
        for row in rows:
            key = (row.category, row.item, row.source_name)
            values = [
                row.category, row.item, row.price, row.unit or "",
                row.source_name, row.source_url, row.collected_at,
                "true", ""
            ]
            if key in existing:
                ws.update(f"A{existing[key]}", [values])
            else:
                ws.append_row(values)

        logger.info(f"[scraper] Upserted {len(rows)} rows into '{worksheet_name}'")
