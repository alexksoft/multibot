# plaster.py — scraper for Штукатурка (plaster)
#
# Each bag of plaster has a weight in KG.
# We normalize price to грн per 1 kg so all bags can be compared fairly.
#
# Example:
#   Bag A: 211 грн / 25 кг  →  price_per_unit = 211 / 25 = 8.44 грн/кг
#   Bag B: 420 грн / 30 кг  →  price_per_unit = 420 / 30 = 14.0 грн/кг
#   → Bag A is cheaper per kg, so it appears first in the sheet
#
# Worksheet columns:
#   item | price | price_unit | weight_kg | price_per_kg | source_name | source_url | collected_at | active | notes
#
# To run just this category:
#   python -m scraper run --category Штукатурка

from ..http_scraper import GenericAIAdapter
from ..base import SheetsWriter

CATEGORY = "Штукатурка"
SOURCE_NAME = "Епіцентр"
URL = "https://epicentrk.ua/ua/shop/shtukaturka/"

# This is the name of the worksheet tab in Google Sheets
WORKSHEET = "Штукатурка"

# Column names for this category's worksheet
HEADER = [
    "item",           # product name
    "price",          # price of one package in грн
    "price_unit",     # always "грн" for plaster
    "weight_kg",      # how many kg in one package
    "price_per_kg",   # price per 1 kg — used for sorting (cheapest first)
    "source_name",    # shop name
    "source_url",     # link to product page
    "collected_at",   # when scraped (YYYY-MM)
    "active",         # true/false
    "notes",          # empty
]


def normalize_price(row) -> float | None:
    """
    Calculate price per 1 kg.
    We need: price (грн) and package weight (kg).
    If package weight is missing — we can't normalize, return None.
    """
    # We need the package weight to normalize
    if not row.package_size or row.package_size <= 0:
        return None

    # Package must be in kg (not m² or litres)
    if (row.package_unit or "").lower() != "кг":
        return None

    # price per 1 kg = total price / kg in package
    return round(row.price / row.package_size, 4)


def to_row(row) -> list:
    """
    Convert a ScrapedRow to a list of values matching HEADER columns.
    """
    return [
        row.item,
        row.price,
        row.price_unit,
        row.package_size or "",   # weight_kg
        row.price_per_unit or "", # price_per_kg
        row.source_name,
        row.source_url,
        row.collected_at,
        "true",
        "",
    ]


async def fetch(kiro_url: str = "", kiro_key: str = "") -> list:
    """Fetch all plaster products and calculate price_per_unit for each."""
    adapter = GenericAIAdapter(
        source_name=SOURCE_NAME,
        base_url="https://epicentrk.ua",
        kiro_url=kiro_url,
        kiro_key=kiro_key,
    )
    rows = await adapter.fetch(CATEGORY, URL)

    # Calculate normalized price for every row
    for row in rows:
        row.price_per_unit = normalize_price(row)

    return rows


def write(writer: SheetsWriter, rows: list) -> None:
    """Write rows to the category worksheet, sorted by price_per_kg."""
    writer.write_category_sheet(WORKSHEET, HEADER, rows, to_row)
