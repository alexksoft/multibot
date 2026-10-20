# tile_glue.py — scraper for Клей (tile adhesive)
#
# Tile glue is sold in bags measured in KG.
# We normalize price to грн per 1 kg.
#
# Example:
#   Bag A: 217 грн / 25 кг  →  price_per_unit = 217 / 25 = 8.68 грн/кг
#   Bag B: 1440 грн / 25 кг →  price_per_unit = 1440 / 25 = 57.6 грн/кг
#   → Bag A is much cheaper per kg
#
# Worksheet columns:
#   item | price | price_unit | weight_kg | price_per_kg | source_name | source_url | collected_at | active | notes
#
# To run just this category:
#   python -m scraper run --category Клей

from ..http_scraper import GenericAIAdapter
from ..base import SheetsWriter

CATEGORY = "Клей"
SOURCE_NAME = "Епіцентр"
URL = "https://epicentrk.ua/ua/shop/kley-dlya-plitki/"
WORKSHEET = "Клей"

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
    """Calculate price per 1 kg."""
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
    """Fetch all tile glue products and calculate price_per_unit for each."""
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
