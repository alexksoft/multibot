# tile_material.py — scraper for Плитка (ceramic tile)
#
# Tile is sold in boxes. Price is already per M² (грн/м²).
# Each box covers a fixed area in m².
# price_per_unit = price (it's already грн/м², no further normalization needed).
#
# Example:
#   Item A: 944 грн/м², box = 1.44 м²  →  price_per_unit = 944
#   Item B: 329 грн/м², box = 1.35 м²  →  price_per_unit = 329
#   → Item B is cheaper per m²
#
# Worksheet columns:
#   item | price | price_unit | box_m2 | weight_kg | price_per_m2 | source_name | source_url | collected_at | active | notes
#
# To run just this category:
#   python -m scraper run --category Плитка

from ..http_scraper import GenericAIAdapter
from ..base import SheetsWriter

CATEGORY = "Плитка"
SOURCE_NAME = "Епіцентр"
URL = "https://epicentrk.ua/ua/shop/plitka/"
WORKSHEET = "Плитка"

HEADER = [
    "item",
    "price",
    "price_unit",     # "грн/м²"
    "box_m2",         # how many m² in one box
    "weight_kg",      # box weight in kg
    "price_per_m2",   # same as price for tile (already per m²) — used for sorting
    "source_name",
    "source_url",
    "collected_at",
    "active",
    "notes",
]


def normalize_price(row):
    """
    For tile, price is already per m².
    So price_per_unit = price directly.
    Only use rows where price_unit is грн/м².
    """
    pu = (row.price_unit or "").lower()
    if "м²" in pu or "m2" in pu:
        return round(row.price, 4)
    # If price is not per m² (e.g. a non-tile item slipped in) — skip
    return None


def to_row(row) -> list:
    return [
        row.item,
        row.price,
        row.price_unit,
        row.package_size or "",   # box_m2 (package_unit should be м²)
        row.volume_l or "",       # weight_kg stored in volume_l? No — use package_size
        row.price_per_unit or "",
        row.source_name,
        row.source_url,
        row.collected_at,
        "true",
        "",
    ]


async def fetch(kiro_url: str = "", kiro_key: str = "") -> list:
    """Fetch all tile products and calculate price_per_unit for each."""
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
    Read the Плитка worksheet and return CatalogItem objects.
    box_m2 = m² per box, price is already грн/м².
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
                box_m2_raw = row.get("box_m2", "")
                box_m2 = float(str(box_m2_raw).replace(",", ".")) if box_m2_raw not in ("", None) else None
                result.append(CatalogItem(
                    category=CATEGORY,
                    item=str(row.get("item", "")).strip(),
                    price=price,
                    unit=str(row.get("price_unit", "грн/м²")).strip(),
                    source_name=str(row.get("source_name", "")).strip() or None,
                    source_url=str(row.get("source_url", "")).strip() or None,
                    collected_at=str(row.get("collected_at", "")).strip() or None,
                    package_size=box_m2,
                    package_unit="м²" if box_m2 else None,
                ))
            except Exception:
                continue
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"[{CATEGORY}] load_items failed: {e}")
    return result
