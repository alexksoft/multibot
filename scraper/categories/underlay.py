# underlay.py — scraper for Підкладка (underlay for laminate)
#
# This file is responsible for ONE category only: Підкладка.
# Underlay is sold in rolls. Price can be per м² or per roll.
# To run just this category manually:
#   python -m scraper run --category Підкладка

from ..http_scraper import GenericAIAdapter

CATEGORY = "Підкладка"
SOURCE_NAME = "Епіцентр"
URL = "https://epicentrk.ua/ua/shop/podlozhka/fs/naznachenie-pod-laminat/"


async def fetch(kiro_url: str = "", kiro_key: str = "") -> list:
    """
    Fetch all underlay products from Epicentr.
    Returns a list of ScrapedRow objects ready to write to Google Sheet.
    """
    adapter = GenericAIAdapter(
        source_name=SOURCE_NAME,
        base_url="https://epicentrk.ua",
        kiro_url=kiro_url,
        kiro_key=kiro_key,
    )
    return await adapter.fetch(CATEGORY, URL)
