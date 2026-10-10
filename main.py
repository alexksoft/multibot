"""
Practical AI Assistants — multi-bot entry point.
Usage: python main.py
"""
import asyncio
import logging
import os

from src.multibot.config.loader import load_configs
from src.multibot.config.settings import settings
from src.multibot.core.logging_setup import setup_logging
from src.multibot.core.storage import SqliteStorage
from src.multibot.manager import BotManager


def _ensure_price_tabs(configs, logger) -> None:
    """Create {bot_name}_prices tab in Google Sheets for every bot that has sheets enabled."""
    import os
    creds = settings.google_creds_path
    if not os.path.exists(creds):
        logger.warning("[startup] Google creds not found, skipping tab creation")
        return
    try:
        from scraper.base import SheetsWriter
    except ImportError:
        return
    for cfg in configs:
        if not cfg.knowledge.sheets.enabled:
            continue
        sheet_id = os.environ.get(cfg.knowledge.sheets.sheet_id_env, "") or settings.google_sheet_id
        if not sheet_id:
            logger.warning(f"[startup] No sheet_id for '{cfg.name}', skipping tab creation")
            continue
        tab_name = f"{cfg.name}_prices"
        try:
            writer = SheetsWriter(creds, sheet_id)
            writer.ensure_tab_exists(tab_name)
        except Exception as e:
            logger.warning(f"[startup] Could not ensure tab '{tab_name}': {e}")


async def main() -> None:
    setup_logging(settings.log_level)
    logger = logging.getLogger(__name__)
    logger.info("Starting Practical AI Assistants multibot")

    storage = SqliteStorage(settings.db_path)
    await storage.init()

    configs = load_configs(settings.bots_dir)
    if not configs:
        logger.error("No valid bot configs found. Check bots/ directory and .env tokens.")
        return

    # Ensure Google Sheets price tabs exist for all bots that have sheets enabled
    _ensure_price_tabs(configs, logger)

    manager = BotManager(configs, storage, settings)
    manager.build()

    try:
        await manager.run_all()
    finally:
        await storage.close()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
