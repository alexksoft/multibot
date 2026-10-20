# tile_material.py — scraper for Плитка (ceramic tile)
#
# This file is responsible for ONE category only: Плитка.
# Tile is sold in boxes — the scraper reads м² per box from the product page.
# Price will be stored as грн/м² (price per square metre).
# To run just this category manually:
#   python -m scraper run --category Плитка

from ..http_scraper import GenericAIAdapter

CATEGORY = "Плитка"
SOURCE_NAME = "Епіцентр"
URL = "https://epicentrk.ua/ua/shop/plitka/"


async def fetch(kiro_url: str = "", kiro_key: str = "") -> list:
    """
    Fetch all tile products from Epicentr.
    Returns a list of ScrapedRow objects ready to write to Google Sheet.
    Package unit will be "м²" (area per box).
    Price unit will be "грн/м²".
    """
    adapter = GenericAIAdapter(
        source_name=SOURCE_NAME,
        base_url="https://epicentrk.ua",
        kiro_url=kiro_url,
        kiro_key=kiro_key,
    )
    return await adapter.fetch(CATEGORY, URL)
