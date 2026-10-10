"""
Practical AI Assistants — multi-bot entry point.
Usage: python main.py
"""
import asyncio
import logging

from src.multibot.config.loader import load_configs
from src.multibot.config.settings import settings
from src.multibot.core.logging_setup import setup_logging
from src.multibot.core.storage import SqliteStorage
from src.multibot.manager import BotManager


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

    manager = BotManager(configs, storage, settings)
    manager.build()

    try:
        await manager.run_all()
    finally:
        await storage.close()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
