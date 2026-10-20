# fiber.py — scraper for Фібра (fibre for concrete / screed reinforcement)
#
# This file is responsible for ONE category only: Фібра.
# Fibre is sold in small bags measured in KG.
# To run just this category manually:
#   python -m scraper run --category Фібра

from ..http_scraper import GenericAIAdapter

CATEGORY = "Фібра"
SOURCE_NAME = "Епіцентр"
URL = "https://epicentrk.ua/ua/shop/fibra-stroitelnaya/"


async def fetch(kiro_url: str = "", kiro_key: str = "") -> list:
    """
    Fetch all fibre products from Epicentr.
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
