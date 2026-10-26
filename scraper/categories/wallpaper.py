from typing import Optional
# wallpaper.py — scraper for Шпалери (wallpaper)
#
# CHANGELOG:
#   v2 (2026-10): roll_m2 extracted from product page characteristics
#                 (Ширина рулону × Довжина рулону), NOT from product name.
#                 price stays per roll (грн/рул), price_per_m2 used only for sorting.
#                 Excluded: "Шпалери під фарбування", "Шпалери самоклейкі"
#   v1 (original): stored weight_kg, sorted by price_per_roll
#
# HOW IT WORKS:
#   - http_scraper._extract_pkg_from_chars() reads "Ширина рулону" and "Довжина рулону"
#     from the product page and stores width × length as package_size (м²)
#   - price = per roll (грн) — NOT converted to per-m²
#   - price_per_unit = price / roll_m2 — used for sorting cheapest per m² first
#     (fair comparison: 0.53m roll vs 1.06m roll)
#
# Example:
#   Roll A: 144 грн, 0.53×10.05 = 5.33 m²  → price_per_m2 = 27.0 грн/м²
#   Roll B: 830 грн, 1.06×10.05 = 10.65 m² → price_per_m2 = 77.9 грн/м²
#   → Roll A is cheaper per m² despite lower absolute price
#
# Worksheet columns:
#   item | price | price_unit | roll_m2 | price_per_m2 | source_name | source_url | collected_at | active | notes
#
# To run just this category:
#   python -m scraper run --category Шпалери

from ..http_scraper import GenericAIAdapter
from ..base import SheetsWriter

CATEGORY = "Шпалери"
SOURCE_NAME = "Епіцентр"
URL = "https://epicentrk.ua/ua/shop/oboi/"
WORKSHEET = "Шпалери"

HEADER = [
    "item",
    "price",
    "price_unit",     # "грн" (per roll)
    "roll_m2",        # m² per roll = Ширина рулону × Довжина рулону
    "price_per_m2",   # price / roll_m2 — for sorting (cheapest per m² first)
    "source_name",
    "source_url",
    "collected_at",
    "active",
    "notes",
]

# Items to exclude
_EXCLUDE = ("Шпалери під фарбування", "Шпалери самоклейкі")


def normalize_price(row) -> Optional[float]:
    """
    Returns price per m² for sorting.
    row.price stays as per-roll price for display.
    """
    if not row.price or row.price <= 0:
        return None
    if row.package_size and row.package_size > 0:
        return round(row.price / row.package_size, 4)
    return round(row.price, 4)  # fallback if roll_m2 not found


def to_row(row) -> list:
    return [
        row.item,
        row.price,
        row.price_unit,
        row.package_size or "",   # roll_m2
        row.price_per_unit or "", # price_per_m2
        row.source_name,
        row.source_url,
        row.collected_at,
        "true",
        "",
    ]


async def fetch(kiro_url: str = "", kiro_key: str = "") -> list:
    """Fetch wallpaper products, exclude non-standard types, calculate price_per_m2."""
    adapter = GenericAIAdapter(
        source_name=SOURCE_NAME,
        base_url="https://epicentrk.ua",
        kiro_url=kiro_url,
        kiro_key=kiro_key,
    )
    rows = await adapter.fetch(CATEGORY, URL)
    rows = [r for r in rows if not r.item.startswith(_EXCLUDE)]
    for row in rows:
        row.price_per_unit = normalize_price(row)
    return rows


def write(writer: SheetsWriter, rows: list) -> None:
    """Write rows sorted by price_per_m2 (cheapest per m² first)."""
    writer.write_category_sheet(WORKSHEET, HEADER, rows, to_row)
