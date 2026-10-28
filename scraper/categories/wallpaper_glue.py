from typing import Optional
# wallpaper_glue.py — scraper for Клей для шпалер (wallpaper glue)
#
# Wallpaper glue is sold in packets measured in KG.
# We normalize price to грн per 1 kg.
#
# Example:
#   Pack A: 78 грн / 0.095 кг  →  price_per_unit = 78 / 0.095 = 821 грн/кг
#   Pack B: 940 грн / 5 кг     →  price_per_unit = 940 / 5 = 188 грн/кг
#   → Pack B is much cheaper per kg (bulk pack)
#
# Worksheet columns:
#   item | price | price_unit | weight_kg | price_per_kg | source_name | source_url | collected_at | active | notes
#
# To run just this category:
#   python -m scraper run --category "Клей для шпалер"

from ..http_scraper import GenericAIAdapter
from ..base import SheetsWriter

CATEGORY = "Клей для шпалер"
SOURCE_NAME = "Епіцентр"
URL = "https://epicentrk.ua/ua/shop/kley-dlya-oboev/"
WORKSHEET = "Клей для шпалер"

HEADER = [
    "item",
    "price",
    "price_unit",
    "volume_l",       # volume in liters per package
    "coverage_m2",    # Витрата з однієї упаковки (кв. м) — used for package count
    "price_per_m2",   # price / coverage_m2 — for sorting
    "source_name",
    "source_url",
    "collected_at",
    "active",
    "notes",
]


def normalize_price(row) -> Optional[float]:
    """Calculate price per m² coverage for sorting."""
    coverage = row.package_size if row.package_unit == "м²" else None
    if coverage and coverage > 0 and row.price and row.price > 0:
        return round(row.price / coverage, 4)
    return None


def to_row(row) -> list:
    vol = row.volume_l
    coverage = row.package_size if row.package_unit == "м²" else None
    price_per_m2 = row.price_per_unit
    return [
        row.item,
        row.price,
        row.price_unit,
        vol or "",
        coverage or "",
        price_per_m2 or "",
        row.source_name,
        row.source_url,
        row.collected_at,
        "true",
        "",
    ]


async def fetch(kiro_url: str = "", kiro_key: str = "") -> list:
    """Fetch all wallpaper glue products and calculate price_per_unit for each."""
    adapter = GenericAIAdapter(
        source_name=SOURCE_NAME,
        base_url="https://epicentrk.ua",
        kiro_url=kiro_url,
        kiro_key=kiro_key,
    )
    rows = await adapter.fetch(CATEGORY, URL)
    _EXCLUDE = ("PUFAS Ґрунтівка під шпалери Tapet-Grunt", "Клей для склошпалер", "Клей для склополотна",)
    rows = [r for r in rows if not r.item.startswith(_EXCLUDE)]
##    rows = [r for r in rows if r.volume_l and r.volume_l >= 5]
    rows = [r for r in rows if r.coverage_m2]
    for row in rows:
        row.price_per_unit = normalize_price(row)
    return rows


def write(writer: SheetsWriter, rows: list) -> None:
    """Write rows to the category worksheet, sorted by price_per_kg."""
    writer.write_category_sheet(WORKSHEET, HEADER, rows, to_row)
