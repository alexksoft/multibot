# putty.py — scraper for Шпаклівка (putty / wall filler)
#
# Each bag of putty has a weight in KG.
# We normalize price to грн per 1 kg so all bags can be compared fairly.
#
# Example:
#   Bag A: 375 грн / 25 кг  →  price_per_unit = 375 / 25 = 15.0 грн/кг
#   Bag B: 112 грн / 1.4 кг →  price_per_unit = 112 / 1.4 = 80.0 грн/кг
#   → Bag A is much cheaper per kg
#
# Worksheet columns:
#   item | price | price_unit | weight_kg | price_per_kg | source_name | source_url | collected_at | active | notes
#
# To run just this category:
#   python -m scraper run --category Шпаклівка

from ..http_scraper import GenericAIAdapter
from ..base import SheetsWriter

CATEGORY = "Шпаклівка"
SOURCE_NAME = "Епіцентр"
URL = "https://epicentrk.ua/ua/shop/shpaklevka/"
WORKSHEET = "Шпаклівка"

HEADER = [
    "item",
    "price",
    "price_unit",
    "weight_kg",
    "price_per_kg",
    "source_name",
    "source_url",
    "collected_at",
    "active",
    "notes",
]


def normalize_price(row) -> float | None:
    """Calculate price per 1 kg. Returns None if package weight is missing."""
    if not row.package_size or row.package_size <= 0:
        return None
    if (row.package_unit or "").lower() != "кг":
        return None
    return round(row.price / row.package_size, 4)


def to_row(row) -> list:
    return [
        row.item,
        row.price,
        row.price_unit,
        row.package_size or "",
        row.price_per_unit or "",
        row.source_name,
        row.source_url,
        row.collected_at,
        "true",
        "",
    ]


async def fetch(kiro_url: str = "", kiro_key: str = "") -> list:
    """Fetch all putty products and calculate price_per_unit for each."""
    adapter = GenericAIAdapter(
        source_name=SOURCE_NAME,
        base_url="https://epicentrk.ua",
        kiro_url=kiro_url,
        kiro_key=kiro_key,
    )
    rows = await adapter.fetch(CATEGORY, URL)
    for row in rows:
        row.price_per_unit = normalize_price(row)
    return rows


def write(writer: SheetsWriter, rows: list) -> None:
    """Write rows to the category worksheet, sorted by price_per_kg."""
    writer.write_category_sheet(WORKSHEET, HEADER, rows, to_row)
