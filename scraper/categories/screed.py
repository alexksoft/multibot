# screed.py — scraper for Цементна стяжка (cement floor screed)
#
# This file is responsible for ONE category only: Цементна стяжка.
# Screed is sold in heavy bags measured in KG (usually 25 kg per bag).
# To run just this category manually:
#   python -m scraper run --category "Цементна стяжка"

from ..http_scraper import GenericAIAdapter

CATEGORY = "Цементна стяжка"
SOURCE_NAME = "Епіцентр"
URL = "https://epicentrk.ua/ua/shop/styazhka/fs/osnova-cementnaya/"


async def fetch(kiro_url: str = "", kiro_key: str = "") -> list:
    """
    Fetch all cement screed products from Epicentr.
    Returns a list of ScrapedRow objects ready to write to Google Sheet.
    Package unit will be "кг".
    """
    adapter = GenericAIAdapter(
        source_name=SOURCE_NAME,
        base_url="https://epicentrk.ua",
        kiro_url=kiro_url,
        kiro_key=kiro_key,
    )
    return await adapter.fetch(CATEGORY, URL)
