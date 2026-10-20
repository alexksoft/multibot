# plaster.py — scraper for Штукатурка (plaster)
#
# This file is responsible for ONE category only: Штукатурка.
# It knows:
#   - what the category is called (must match Google Sheet exactly)
#   - where to find it on Epicentr website
#   - how to fetch the products (uses shared logic from http_scraper.py)
#
# To run just this category manually:
#   python -m scraper run --category Штукатурка

from ..http_scraper import GenericAIAdapter

# The category name — must match exactly what is in Google Sheet column "category"
CATEGORY = "Штукатурка"

# The shop name — shown in Google Sheet column "source_name"
SOURCE_NAME = "Епіцентр"

# The URL of the category page on Epicentr
URL = "https://epicentrk.ua/ua/shop/shtukaturka/"


async def fetch(kiro_url: str = "", kiro_key: str = "") -> list:
    """
    Fetch all plaster products from Epicentr.
    Returns a list of ScrapedRow objects ready to write to Google Sheet.
    """
    # GenericAIAdapter does all the hard work:
    #   - fetches multiple pages
    #   - parses JSON-LD product data
    #   - visits each product page to get package_size, package_unit, volume
    adapter = GenericAIAdapter(
        source_name=SOURCE_NAME,
        base_url="https://epicentrk.ua",
        kiro_url=kiro_url,
        kiro_key=kiro_key,
    )
    return await adapter.fetch(CATEGORY, URL)
