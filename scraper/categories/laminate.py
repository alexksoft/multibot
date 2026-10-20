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
    "weight_kg",      # box weight in kg (box m² coverage not always available)
    "price_per_m2",   # same as price — used for sorting
    "source_name",
    "source_url",
    "collected_at",
    "active",
    "notes",
]


def normalize_price(row):
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


def load_items(creds_path: str, sheet_id: str) -> list:
    """
    Read the Ламінат worksheet and return CatalogItem objects.
    Price is грн/м². weight_kg = box weight (box m² coverage not always available).
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
                    unit=str(row.get("price_unit", "грн/м²")).strip(),
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
