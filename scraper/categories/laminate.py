# laminate.py — scraper for Ламінат (laminate flooring)
#
# This file is responsible for ONE category only: Ламінат.
# Laminate is sold in boxes. Price is per м².
# The scraper will try to read м² per box from the product page.
# To run just this category manually:
#   python -m scraper run --category Ламінат

from ..http_scraper import GenericAIAdapter

CATEGORY = "Ламінат"
SOURCE_NAME = "Епіцентр"
URL = "https://epicentrk.ua/ua/shop/laminat/"


async def fetch(kiro_url: str = "", kiro_key: str = "") -> list:
    """
    Fetch all laminate products from Epicentr.
    Returns a list of ScrapedRow objects ready to write to Google Sheet.
    Price unit will be "грн/м²".
    Package unit will be "м²" if found on product page, "кг" (box weight) otherwise.
    """
    adapter = GenericAIAdapter(
        source_name=SOURCE_NAME,
        base_url="https://epicentrk.ua",
        kiro_url=kiro_url,
        kiro_key=kiro_key,
    )
    return await adapter.fetch(CATEGORY, URL)
