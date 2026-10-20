# wallpaper.py — scraper for Шпалери (wallpaper)
#
# This file is responsible for ONE category only: Шпалери.
# Wallpaper is sold per roll. Price is per roll (грн).
# To run just this category manually:
#   python -m scraper run --category Шпалери

from ..http_scraper import GenericAIAdapter

CATEGORY = "Шпалери"
SOURCE_NAME = "Епіцентр"
URL = "https://epicentrk.ua/ua/shop/oboi/"


async def fetch(kiro_url: str = "", kiro_key: str = "") -> list:
    """
    Fetch all wallpaper products from Epicentr.
    Returns a list of ScrapedRow objects ready to write to Google Sheet.
    Price unit will be "грн" (per roll).
    """
    adapter = GenericAIAdapter(
        source_name=SOURCE_NAME,
        base_url="https://epicentrk.ua",
        kiro_url=kiro_url,
        kiro_key=kiro_key,
    )
    return await adapter.fetch(CATEGORY, URL)
