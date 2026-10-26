from typing import Optional
# fiber.py — scraper for Фібра (fibre for concrete reinforcement)
#
# Fibre is sold in small bags measured in KG.
# We normalize price to грн per 1 kg.
#
# Example:
#   Bag A: 160 грн / 0.9 кг  →  price_per_unit = 160 / 0.9 = 177.8 грн/кг
#   Bag B: 245 грн / 1 кг    →  price_per_unit = 245 / 1 = 245 грн/кг
#   → Bag A is cheaper per kg
#
# Worksheet columns:
#   item | price | price_unit | weight_kg | price_per_kg | source_name | source_url | collected_at | active | notes
#
# To run just this category:
#   python -m scraper run --category Фібра

from ..http_scraper import GenericAIAdapter
from ..base import SheetsWriter

CATEGORY = "Фібра"
SOURCE_NAME = "Епіцентр"
URL = "https://epicentrk.ua/ua/shop/fibra-stroitelnaya/"
WORKSHEET = "Фібра"

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
    """Fetch all fibre products and calculate price_per_unit for each."""
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
