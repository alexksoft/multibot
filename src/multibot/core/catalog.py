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


class MultiCategorySheetsCatalog:
    """
    Loads items from Google Sheets by calling load_items() on each calculator module.
    Each calculator knows its own worksheet name and column structure.
    No parsing logic here — that belongs to each calculator.
    """

    def __init__(self, creds_path: str, sheet_id: str, ttl: int):
        self._creds_path = creds_path
        self._sheet_id = sheet_id
        self._ttl = ttl
        self._cache: list[CatalogItem] = []
        self._cache_time: float = 0.0

    async def items(self) -> list[CatalogItem]:
        now = time.monotonic()
        if self._cache and (now - self._cache_time) < self._ttl:
            return self._cache

        # Each calculator module knows its own worksheet and columns
        from ..capabilities.calculators import (
            plaster, putty, primer, paint,
            tile_material, tile_glue, grout,
            screed, fiber,
            laminate, underlay,
            wallpaper, wallpaper_glue,
        )

        all_modules = [
            plaster, putty, primer, paint,
            tile_material, tile_glue, grout,
            screed, fiber,
            laminate, underlay,
            wallpaper, wallpaper_glue,
        ]

        all_items = []
        for mod in all_modules:
            try:
                items = mod.load_items(self._creds_path, self._sheet_id)
                all_items.extend(items)
                logger.info(f"[catalog] {mod.CATEGORY}: {len(items)} items")
            except Exception as e:
                logger.warning(f"[catalog] Failed to load {mod.CATEGORY}: {e}")

        self._cache = all_items
        self._cache_time = now
        logger.info(f"[catalog] Total: {len(self._cache)} items loaded")
        return self._cache


def make_catalog_provider(
    sheets_cfg: SheetsSource,
    local_items: list[CatalogItem],
    creds_path: str,
) -> CatalogProvider:
    """Return MultiCategorySheetsCatalog if enabled, else LocalCatalog."""
    if sheets_cfg.enabled:
        sheet_id = os.environ.get(sheets_cfg.sheet_id_env, "")
        if sheet_id:
            return MultiCategorySheetsCatalog(creds_path, sheet_id, sheets_cfg.cache_ttl_seconds)
        logger.warning(f"[catalog] sheets.enabled but env '{sheets_cfg.sheet_id_env}' not set, using local")
    return LocalCatalog(local_items)
