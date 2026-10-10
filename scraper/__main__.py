"""
Scraper CLI: python -m scraper run [--category CATEGORY] [--sheet SHEET_ID]

Runs independently from bots. Writes real market data into Google Sheets.
Bots are read-only consumers of that data.
"""
from __future__ import annotations
import argparse
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scraper.adapters.building import BuildingMaterialsAdapter
from scraper.base import SheetsWriter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CATEGORIES = ["Фарба", "Штукатурка", "Шпаклівка", "Ґрунтовка"]
WORKSHEET = "Матеріали"


async def run(categories: list[str], sheet_id: str, creds_path: str) -> None:
    adapter = BuildingMaterialsAdapter()
    writer = SheetsWriter(creds_path, sheet_id)
    all_rows = []

    for cat in categories:
        logger.info(f"[scraper] Fetching category: {cat}")
        try:
            rows = await adapter.fetch(cat)
            logger.info(f"[scraper] Got {len(rows)} rows for '{cat}'")
            all_rows.extend(rows)
        except Exception as e:
            logger.error(f"[scraper] Failed '{cat}': {e}")

    if all_rows:
        try:
            writer.upsert(WORKSHEET, all_rows)
        except Exception as e:
            logger.error(f"[scraper] Sheets write failed: {e}")
    else:
        logger.warning("[scraper] No rows collected")


def main() -> None:
    parser = argparse.ArgumentParser(description="Scraper for Practical AI Assistants")
    sub = parser.add_subparsers(dest="command")
    run_cmd = sub.add_parser("run", help="Run scraper")
    run_cmd.add_argument("--category", nargs="*", help="Categories to scrape (default: all)")
    run_cmd.add_argument("--sheet", help="Google Sheet ID (overrides env BUILDING_SHEET_ID)")
    args = parser.parse_args()

    if args.command != "run":
        parser.print_help()
        return

    from dotenv import load_dotenv
    load_dotenv()

    sheet_id = args.sheet or os.environ.get("BUILDING_SHEET_ID", "")
    creds_path = os.environ.get("GOOGLE_CREDS_PATH", "config/google-service-account.json")
    categories = args.category or CATEGORIES

    if not sheet_id:
        logger.error("BUILDING_SHEET_ID not set. Use --sheet or set env var.")
        sys.exit(1)

    asyncio.run(run(categories, sheet_id, creds_path))


if __name__ == "__main__":
    main()
