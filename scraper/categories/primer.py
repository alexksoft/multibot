# primer.py — scraper for Ґрунтовка (primer / ground coat)
#
# Primer is a LIQUID sold in cans.
# We normalize price to грн per 1 LITRE so all cans can be compared fairly.
# The scraper reads BOTH volume_l (litres) and package_size (weight in kg).
#
# Normalization priority:
#   1. Use volume_l if found on product page (most accurate)
#   2. If only weight (kg) found — we can't convert kg to litres reliably, skip
#
# Example:
#   Can A: 1059 грн, volume_l = 3 л  →  price_per_unit = 1059 / 3 = 353 грн/л
#   Can B: 420 грн,  volume_l = 10 л →  price_per_unit = 420 / 10 = 42 грн/л
#   → Can B is much cheaper per litre
#
# Worksheet columns:
#   item | price | price_unit | volume_l | weight_kg | price_per_l | source_name | source_url | collected_at | active | notes
#
# To run just this category:
#   python -m scraper run --category Ґрунтовка

from ..http_scraper import GenericAIAdapter
from ..base import SheetsWriter

CATEGORY = "Ґрунтовка"
SOURCE_NAME = "Епіцентр"
URL = "https://epicentrk.ua/ua/shop/gruntovka/"
WORKSHEET = "Ґрунтовка"

HEADER = [
    "item",
    "price",
    "price_unit",
    "volume_l",       # litres per can (from product page об'єм field)
    "weight_kg",      # weight of can in kg (from product page вага field)
    "price_per_l",    # price per 1 litre — used for sorting
    "source_name",
    "source_url",
    "collected_at",
    "active",
    "notes",
]


def normalize_price(row) -> float | None:
    """
    Calculate price per 1 litre.
    Uses volume_l first (most accurate).
    Returns None if volume is unknown.
    """
    # Best case: we have the volume in litres from the product page
    if row.volume_l and row.volume_l > 0:
        return round(row.price / row.volume_l, 4)

    # Can't normalize without volume — weight in kg ≠ volume in litres
    return None


def to_row(row) -> list:
    return [
        row.item,
        row.price,
        row.price_unit,
        row.volume_l or "",       # volume_l
        row.package_size or "",   # weight_kg
        row.price_per_unit or "", # price_per_l
        row.source_name,
        row.source_url,
        row.collected_at,
        "true",
        "",
    ]


async def fetch(kiro_url: str = "", kiro_key: str = "") -> list:
    """Fetch all primer products and calculate price_per_unit for each."""
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
    """Write rows to the category worksheet, sorted by price_per_l."""
    writer.write_category_sheet(WORKSHEET, HEADER, rows, to_row)
