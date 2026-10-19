from __future__ import annotations
import logging
import os
import time
from typing import Protocol, runtime_checkable

from ..config.sections import CatalogItem, SheetsSource

logger = logging.getLogger(__name__)


@runtime_checkable
class CatalogProvider(Protocol):
    async def items(self) -> list[CatalogItem]: ...


class LocalCatalog:
    def __init__(self, items: list[CatalogItem]):
        self._items = items

    async def items(self) -> list[CatalogItem]:
        return [i for i in self._items if i.active]


class GoogleSheetsCatalog:
    """
    Reads the real-data matrix from Google Sheets and caches it.
    Expected columns: category|item|price|unit|source_name|source_url|collected_at|active|notes
    Rows with price but no source_name are discarded (unreliable price).
    """

    def __init__(self, creds_path: str, sheet_id: str,
                 worksheet: str | None, ttl: int):
        self._creds_path = creds_path
        self._sheet_id = sheet_id
        self._worksheet = worksheet
        self._ttl = ttl
        self._cache: list[CatalogItem] = []
        self._cache_time: float = 0.0

    def _get_client(self):
        if not self._creds_path or not self._sheet_id:
            return None
        if not os.path.exists(self._creds_path):
            logger.warning(f"[catalog] Google creds not found: {self._creds_path}")
            return None
        try:
            import gspread
            return gspread.service_account(filename=self._creds_path)
        except Exception as e:
            logger.warning(f"[catalog] gspread init failed: {e}")
            return None

    def _parse_row(self, row: dict) -> CatalogItem | None:
        def _bool(v) -> bool:
            return str(v).strip().lower() in ("true", "1", "так", "yes")

        try:
            price_raw = row.get("price", "")
            price = float(str(price_raw).replace(",", ".")) if price_raw not in ("", None) else None
            source_name = str(row.get("source_name", "")).strip() or None
            if price is not None and not source_name:
                return None
            active_raw = row.get("active", "true")
            # price_unit column (new) falls back to legacy unit column
            price_unit = str(row.get("price_unit", "")).strip() or str(row.get("unit", "")).strip() or "грн"
            package_size_raw = row.get("package_size", "")
            package_size = float(str(package_size_raw).replace(",", ".")) if package_size_raw not in ("", None) else None
            package_unit = str(row.get("package_unit", "")).strip() or None
            return CatalogItem(
                category=str(row.get("category", "")).strip(),
                item=str(row.get("item", "")).strip(),
                price=price,
                unit=price_unit,
                source_name=source_name,
                source_url=str(row.get("source_url", "")).strip() or None,
                collected_at=str(row.get("collected_at", "")).strip() or None,
                package_size=package_size,
                package_unit=package_unit,
                attributes={},
                active=_bool(active_raw),
                notes=str(row.get("notes", "")).strip(),
            )
        except Exception as e:
            logger.debug(f"[catalog] Skipping row: {e}")
            return None

    async def items(self) -> list[CatalogItem]:
        now = time.monotonic()
        if self._cache and (now - self._cache_time) < self._ttl:
            return self._cache

        gc = self._get_client()
        if gc is None:
            logger.warning("[catalog] Google Sheets unavailable, using cache/fallback")
            return self._cache

        try:
            spreadsheet = gc.open_by_key(self._sheet_id)
            ws = spreadsheet.worksheet(self._worksheet) if self._worksheet else spreadsheet.sheet1
            rows = ws.get_all_records()
            parsed = [self._parse_row(r) for r in rows]
            self._cache = [i for i in parsed if i is not None and i.active]
            self._cache_time = now
            logger.info(f"[catalog] Loaded {len(self._cache)} active items from Sheets")
        except Exception as e:
            logger.warning(f"[catalog] Sheets read failed: {e}, using cache")

        return self._cache


def make_catalog_provider(
    sheets_cfg: SheetsSource,
    local_items: list[CatalogItem],
    creds_path: str,
) -> CatalogProvider:
    """Return GoogleSheetsCatalog if enabled, else LocalCatalog."""
    if sheets_cfg.enabled:
        sheet_id = os.environ.get(sheets_cfg.sheet_id_env, "")
        if sheet_id:
            return GoogleSheetsCatalog(creds_path, sheet_id, sheets_cfg.worksheet, sheets_cfg.cache_ttl_seconds)
        logger.warning(f"[catalog] sheets.enabled but env '{sheets_cfg.sheet_id_env}' not set, using local")
    return LocalCatalog(local_items)
