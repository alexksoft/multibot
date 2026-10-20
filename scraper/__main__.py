"""
Scraper entry point.
Usage:
    python -m scraper run                          # scrape all 13 categories
    python -m scraper run --category Штукатурка    # scrape one category
    python -m scraper run --category Фарба Клей    # scrape several categories

Each category has its own file in scraper/categories/.
All results are written to Google Sheet (worksheet = building_assistant_prices).
"""
from __future__ import annotations
import argparse
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import every category module — one file per category
from scraper.categories import (
    plaster,        # Штукатурка
    putty,          # Шпаклівка
    primer,         # Ґрунтовка
    paint,          # Фарба
    tile_material,  # Плитка
    tile_glue,      # Клей
    grout,          # Затирка
    screed,         # Цементна стяжка
    fiber,          # Фібра
    laminate,       # Ламінат
    underlay,       # Підкладка
    wallpaper,      # Шпалери
    wallpaper_glue, # Клей для шпалер
)
from scraper.base import SheetsWriter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# All category modules in one list — easy to add new ones here
ALL_CATEGORIES = [
    plaster,
    putty,
    primer,
    paint,
    tile_material,
    tile_glue,
    grout,
    screed,
    fiber,
    laminate,
    underlay,
    wallpaper,
    wallpaper_glue,
]

async def run(category_names: list[str], sheet_id: str, creds_path: str,
              kiro_url: str, kiro_key: str) -> None:
    """
    Run scraper for the given category names (or all if list is empty).
    Writes all results to Google Sheet in one batch.
    """

    # Decide which category modules to run
    if category_names:
        # User asked for specific categories — find matching modules
        modules_to_run = [
            m for m in ALL_CATEGORIES
            if m.CATEGORY in category_names
        ]
        # Warn if any requested category was not found
        found_names = [m.CATEGORY for m in modules_to_run]
        for name in category_names:
            if name not in found_names:
                logger.warning(f"[scraper] Unknown category: '{name}' — skipping")
    else:
        # No filter — run all categories
        modules_to_run = ALL_CATEGORIES

    if not modules_to_run:
        logger.error("[scraper] No categories to run")
        return

    # Fetch products from each category one by one
    all_rows = []
    for mod in modules_to_run:
        logger.info(f"[scraper] Starting category: {mod.CATEGORY}")
        try:
            rows = await mod.fetch(kiro_url=kiro_url, kiro_key=kiro_key)
            logger.info(f"[scraper] {mod.CATEGORY}: got {len(rows)} items")
            all_rows.extend(rows)
        except Exception as e:
            logger.error(f"[scraper] {mod.CATEGORY} failed: {e}")

    # Write each category to its own worksheet
    if all_rows:
        logger.info(f"[scraper] Writing {len(all_rows)} total rows to individual category sheets...")
        # Group rows by category module
        rows_by_module = {}
        for mod in modules_to_run:
            rows_by_module[mod.CATEGORY] = []
        for row in all_rows:
            if row.category in rows_by_module:
                rows_by_module[row.category].append(row)

        writer = SheetsWriter(creds_path, sheet_id)
        for mod in modules_to_run:
            cat_rows = rows_by_module.get(mod.CATEGORY, [])
            if cat_rows:
                try:
                    mod.write(writer, cat_rows)
                    logger.info(f"[scraper] {mod.CATEGORY}: wrote {len(cat_rows)} rows")
                except Exception as e:
                    logger.error(f"[scraper] {mod.CATEGORY} sheet write failed: {e}")
    else:
        logger.warning("[scraper] No rows collected — sheets not updated")


def main() -> None:
    parser = argparse.ArgumentParser(description="Building materials price scraper")
    sub = parser.add_subparsers(dest="command")

    run_cmd = sub.add_parser("run", help="Run the scraper")
    run_cmd.add_argument(
        "--category", nargs="*",
        help="Category names to scrape (default: all). Example: --category Фарба Клей"
    )
    run_cmd.add_argument("--sheet", help="Google Sheet ID (overrides env BUILDING_SHEET_ID)")

    args = parser.parse_args()

    if args.command != "run":
        parser.print_help()
        return

    from dotenv import load_dotenv
    load_dotenv()

    sheet_id = args.sheet or os.environ.get("BUILDING_SHEET_ID", "")
    creds_path = os.environ.get("GOOGLE_CREDS_PATH", "config/google-service-account.json")
    kiro_url = os.environ.get("KIRO_GATEWAY_URL", "")
    kiro_key = os.environ.get("KIRO_GATEWAY_API_KEY", "")
    category_names = args.category or []

    if not sheet_id:
        logger.error("BUILDING_SHEET_ID not set. Use --sheet or set env var.")
        sys.exit(1)

    asyncio.run(run(category_names, sheet_id, creds_path, kiro_url, kiro_key))


if __name__ == "__main__":
    main()
