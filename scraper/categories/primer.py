# primer.py — scraper for Ґрунтовка (primer / ground coat)
#
# This file is responsible for ONE category only: Ґрунтовка.
# Primer is a liquid — the scraper will try to read volume (л) from the product page
# so the calculator can figure out how many cans to buy.
# To run just this category manually:
#   python -m scraper run --category Ґрунтовка

from ..http_scraper import GenericAIAdapter

CATEGORY = "Ґрунтовка"
SOURCE_NAME = "Епіцентр"
URL = "https://epicentrk.ua/ua/shop/gruntovka/"


async def fetch(kiro_url: str = "", kiro_key: str = "") -> list:
    """
    Fetch all primer products from Epicentr.
    Returns a list of ScrapedRow objects ready to write to Google Sheet.
    Package unit will be "л" if volume found on product page, "кг" otherwise.
    """
    adapter = GenericAIAdapter(
        source_name=SOURCE_NAME,
        base_url="https://epicentrk.ua",
        kiro_url=kiro_url,
        kiro_key=kiro_key,
    )
    return await adapter.fetch(CATEGORY, URL)
