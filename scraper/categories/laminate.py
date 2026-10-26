from typing import Optional
# laminate.py — scraper for Ламінат (laminate flooring)
#
# Laminate is sold in boxes. Price is per M² (грн/м²).
# price_per_unit = price (already грн/м², no further normalization needed).
# We also store box weight in kg (that's what the scraper finds — box coverage in m²
# is not always available on Epicentr product pages).
#
# Example:
#   Item A: 357 грн/м²  →  price_per_unit = 357
#   Item B: 550 грн/м²  →  price_per_unit = 550
#   → Item A is cheaper per m²
#
# Worksheet columns:
#   item | price | price_unit | weight_kg | price_per_m2 | source_name | source_url | collected_at | active | notes
#
# To run just this category:
#   python -m scraper run --category Ламінат

from ..http_scraper import GenericAIAdapter
from ..base import SheetsWriter

CATEGORY = "Ламінат"
SOURCE_NAME = "Епіцентр"
URL = "https://epicentrk.ua/ua/shop/laminat/"
WORKSHEET = "Ламінат"

HEADER = [
    "item",
    "price",
    "price_unit",     # "грн/м²"
    "box_m2",         # m² coverage per box (Площа в упаковці)
    "price_per_m2",   # same as price — used for sorting
    "source_name",
    "source_url",
    "collected_at",
    "active",
    "notes",
]


def normalize_price(row) -> Optional[float]:
    """
    For laminate, price is already per m².
    price_per_unit = price directly.
    """
    pu = (row.price_unit or "").lower()
    if "м²" in pu or "m2" in pu:
        return round(row.price, 4)
    return None


def to_row(row) -> list:
    return [
        row.item,
        row.price,
        row.price_unit,
        row.package_size or "",   # weight_kg
        row.price_per_unit or "",
        row.source_name,
        row.source_url,
        row.collected_at,
        "true",
        "",
    ]


async def fetch(kiro_url: str = "", kiro_key: str = "") -> list:
    """Fetch all laminate products and calculate price_per_unit for each."""
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
    """Write rows to the category worksheet, sorted by price_per_m2."""
    writer.write_category_sheet(WORKSHEET, HEADER, rows, to_row)
