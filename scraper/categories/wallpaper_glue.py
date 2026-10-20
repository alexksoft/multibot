# wallpaper_glue.py — scraper for Клей для шпалер (wallpaper glue)
#
# This file is responsible for ONE category only: Клей для шпалер.
# Wallpaper glue is sold in packets measured in KG.
# To run just this category manually:
#   python -m scraper run --category "Клей для шпалер"

from ..http_scraper import GenericAIAdapter

CATEGORY = "Клей для шпалер"
SOURCE_NAME = "Епіцентр"
URL = "https://epicentrk.ua/ua/shop/kley-dlya-oboev/"


async def fetch(kiro_url: str = "", kiro_key: str = "") -> list:
    """
    Fetch all wallpaper glue products from Epicentr.
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
