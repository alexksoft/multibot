# putty.py — scraper for Шпаклівка (putty / filler)
#
# This file is responsible for ONE category only: Шпаклівка.
# To run just this category manually:
#   python -m scraper run --category Шпаклівка

from ..http_scraper import GenericAIAdapter

CATEGORY = "Шпаклівка"
SOURCE_NAME = "Епіцентр"
URL = "https://epicentrk.ua/ua/shop/shpaklevka/"


async def fetch(kiro_url: str = "", kiro_key: str = "") -> list:
    """
    Fetch all putty products from Epicentr.
    Returns a list of ScrapedRow objects ready to write to Google Sheet.
    """
    adapter = GenericAIAdapter(
        source_name=SOURCE_NAME,
        base_url="https://epicentrk.ua",
        kiro_url=kiro_url,
        kiro_key=kiro_key,
    )
    return await adapter.fetch(CATEGORY, URL)
