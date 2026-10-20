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


def normalize_price(row):
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


def load_items(creds_path: str, sheet_id: str) -> list:
    """Read the Фібра worksheet and return CatalogItem objects."""
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
