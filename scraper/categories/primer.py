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


def normalize_price(row):
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


def load_items(creds_path: str, sheet_id: str) -> list:
    """
    Read the Ґрунтовка worksheet and return CatalogItem objects.
    Reads both volume_l (litres) and weight_kg so the calculator can use volume.
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
                volume_l_raw = row.get("volume_l", "")
                volume_l = float(str(volume_l_raw).replace(",", ".")) if volume_l_raw not in ("", None) else None
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
                    volume_l=volume_l,
                ))
            except Exception:
                continue
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"[{CATEGORY}] load_items failed: {e}")
    return result
