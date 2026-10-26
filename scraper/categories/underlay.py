from typing import Optional
# underlay.py — scraper for Підкладка (underlay for laminate)
#
# Underlay is sold in rolls. Price can be per M² (грн/м²) or per roll (грн).
# We normalize to грн/м² when possible.
#
# If price is already грн/м²:
#   price_per_unit = price  (already normalized)
#
# If price is грн per roll and we know roll coverage in m²:
#   price_per_unit = price / roll_m2
#   (roll coverage not always available from scraper — stored as package_size if м²)
#
# Example:
#   Roll A: 96 грн/м²           →  price_per_unit = 96
#   Roll B: 1190 грн, 10 м²/рол →  price_per_unit = 1190 / 10 = 119 грн/м²
#   → Roll A is cheaper per m²
#
# Worksheet columns:
#   item | price | price_unit | roll_m2 | weight_kg | price_per_m2 | source_name | source_url | collected_at | active | notes
#
# To run just this category:
#   python -m scraper run --category Підкладка

from ..http_scraper import GenericAIAdapter
from ..base import SheetsWriter

CATEGORY = "Підкладка"
SOURCE_NAME = "Епіцентр"
URL = "https://epicentrk.ua/ua/shop/podlozhka/fs/naznachenie-pod-laminat/"
WORKSHEET = "Підкладка"

HEADER = [
    "item",
    "price",
    "price_unit",
    "roll_m2",        # m² per roll (package_size when package_unit=м²)
    "weight_kg",      # roll weight in kg (package_size when package_unit=кг)
    "price_per_m2",   # normalized price per m² — used for sorting
    "source_name",
    "source_url",
    "collected_at",
    "active",
    "notes",
]


def normalize_price(row) -> Optional[float]:
    """
    Normalize to грн per m².
    Case 1: price already per m² → use directly.
    Case 2: price per roll + package_size in m² → divide.
    """
    pu = (row.price_unit or "").lower()

    # Case 1: price is already per m²
    if "м²" in pu or "m2" in pu:
        return round(row.price, 4)

    # Case 2: price per roll, and we know m² per roll
    if row.package_size and row.package_size > 0:
        pkg_unit = (row.package_unit or "").lower()
        if "м²" in pkg_unit or "m2" in pkg_unit:
            return round(row.price / row.package_size, 4)

    # Can't normalize
    return None


def to_row(row) -> list:
    # Separate roll_m2 and weight_kg based on package_unit
    pkg_unit = (row.package_unit or "").lower()
    if "м²" in pkg_unit or "m2" in pkg_unit:
        roll_m2 = row.package_size or ""
        weight_kg = ""
    else:
        roll_m2 = ""
        weight_kg = row.package_size or ""

    return [
        row.item,
        row.price,
        row.price_unit,
        roll_m2,
        weight_kg,
        row.price_per_unit or "",
        row.source_name,
        row.source_url,
        row.collected_at,
        "true",
        "",
    ]


async def fetch(kiro_url: str = "", kiro_key: str = "") -> list:
    """Fetch all underlay products and calculate price_per_unit for each."""
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
