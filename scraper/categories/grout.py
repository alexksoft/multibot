from typing import Optional
# grout.py — scraper for Затирка (tile grout)
#
# Grout is sold in small bags measured in KG.
# We normalize price to грн per 1 kg.
#
# Example:
#   Pack A: 144 грн / 2 кг   →  price_per_unit = 144 / 2 = 72 грн/кг
#   Pack B: 1718 грн / 1.5 кг → price_per_unit = 1718 / 1.5 = 1145 грн/кг
#   → Pack A is much cheaper (Pack B is epoxy grout — premium product)
#
# Worksheet columns:
#   item | price | price_unit | weight_kg | price_per_kg | source_name | source_url | collected_at | active | notes
#
# To run just this category:
#   python -m scraper run --category Затирка

from ..http_scraper import GenericAIAdapter
from ..base import SheetsWriter

CATEGORY = "Затирка"
SOURCE_NAME = "Епіцентр"
URL = "https://epicentrk.ua/ua/shop/fuga/"
WORKSHEET = "Затирка"

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


def normalize_price(row) -> Optional[float]:
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
    """Fetch all grout products and calculate price_per_unit for each."""
    adapter = GenericAIAdapter(
        source_name=SOURCE_NAME,
        base_url="https://epicentrk.ua",
        kiro_url=kiro_url,
        kiro_key=kiro_key,
    )
    rows = await adapter.fetch(CATEGORY, URL)
    # Exclude non-grout items that appear in this category
    _EXCLUDE_PREFIX = ("Поліпласт", "Олівець")
    rows = [r for r in rows if r.item.startswith("Затірка") and not r.item.startswith(_EXCLUDE_PREFIX)]
    for row in rows:
        row.price_per_unit = normalize_price(row)
    return rows


def write(writer: SheetsWriter, rows: list) -> None:
    """Write rows to the category worksheet, sorted by price_per_kg."""
    writer.write_category_sheet(WORKSHEET, HEADER, rows, to_row)
