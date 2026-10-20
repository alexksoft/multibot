# wallpaper.py — scraper for Шпалери (wallpaper)
#
# Wallpaper is sold per ROLL. Price is per roll (грн).
# Each roll has a width and length — we can calculate m² per roll.
# We normalize price to грн per M² so rolls of different sizes can be compared.
#
# m² per roll = roll_width_m × roll_length_m
# price_per_m2 = price / m²_per_roll
#
# Problem: Epicentr doesn't always expose width/length as structured characteristics.
# The scraper stores roll WEIGHT in kg (package_size). Width/length may be in the name.
# If we can't calculate m² — we still show price per roll for reference.
#
# Example:
#   Roll A: 207 грн, 0.53m × 10.05m = 5.33 m²  →  price_per_m2 = 207 / 5.33 = 38.8 грн/м²
#   Roll B: 923 грн, 1.06m × 10.05m = 10.65 m² →  price_per_m2 = 923 / 10.65 = 86.7 грн/м²
#   → Roll A is cheaper per m²
#
# Worksheet columns:
#   item | price | price_unit | weight_kg | price_per_roll | source_name | source_url | collected_at | active | notes
#
# Note: price_per_roll IS the normalized unit here since all rolls are sold individually.
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
    "weight_kg",      # roll weight in kg
    "price_per_roll", # same as price — used for sorting (cheapest roll first)
    "source_name",
    "source_url",
    "collected_at",
    "active",
    "notes",
]


def normalize_price(row):
    """
    For wallpaper, price is per roll.
    price_per_unit = price (per roll) — used to sort cheapest roll first.
    """
    if row.price and row.price > 0:
        return round(row.price, 4)
    return None


def to_row(row) -> list:
    return [
        row.item,
        row.price,
        row.price_unit,
        row.package_size or "",   # weight_kg
        row.price_per_unit or "", # price_per_roll
        row.source_name,
        row.source_url,
        row.collected_at,
        "true",
        "",
    ]


async def fetch(kiro_url: str = "", kiro_key: str = "") -> list:
    """Fetch all wallpaper products and calculate price_per_unit for each."""
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
    """Write rows to the category worksheet, sorted by price_per_roll."""
    writer.write_category_sheet(WORKSHEET, HEADER, rows, to_row)


def load_items(creds_path: str, sheet_id: str) -> list:
    """
    Read the Шпалери worksheet and return CatalogItem objects.
    Price is per roll (грн). weight_kg = roll weight.
    """
    from src.multibot.config.sections import CatalogItem
    import gspread
    result = []
    try:
        gc = gspread.service_account(filename=creds_path)
        ws = gc.open_by_key(sheet_id).worksheet(WORKSHEET)
        for row in ws.get_all_records():
            if str(row.get("active", "true")).lower() not in ("true", "1", "так"):
                continue
            try:
                price = float(str(row.get("price", "")).replace(",", "."))
                weight_kg_raw = row.get("weight_kg", "")
                weight_kg = float(str(weight_kg_raw).replace(",", ".")) if weight_kg_raw not in ("", None) else None
                result.append(CatalogItem(
                    category=CATEGORY,
                    item=str(row.get("item", "")).strip(),
                    price=price,
                    unit=str(row.get("price_unit", "грн")).strip(),
                    source_name=str(row.get("source_name", "")).strip() or None,
                    source_url=str(row.get("source_url", "")).strip() or None,
                    collected_at=str(row.get("collected_at", "")).strip() or None,
                    package_size=weight_kg,
                    package_unit="кг" if weight_kg else None,
                ))
            except Exception:
                continue
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"[{CATEGORY}] load_items failed: {e}")
    return result
