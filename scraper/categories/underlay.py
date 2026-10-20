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


def normalize_price(row):
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


def load_items(creds_path: str, sheet_id: str) -> list:
    """
    Read the Підкладка worksheet and return CatalogItem objects.
    roll_m2 = m² per roll when available. weight_kg = roll weight.
    Price can be грн/м² or грн per roll.
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
                roll_m2_raw = row.get("roll_m2", "")
                roll_m2 = float(str(roll_m2_raw).replace(",", ".")) if roll_m2_raw not in ("", None) else None
                weight_kg_raw = row.get("weight_kg", "")
                weight_kg = float(str(weight_kg_raw).replace(",", ".")) if weight_kg_raw not in ("", None) else None
                # Use roll_m2 as package_size if available, else weight_kg
                if roll_m2:
                    pkg_size, pkg_unit = roll_m2, "м²"
                else:
                    pkg_size, pkg_unit = weight_kg, ("кг" if weight_kg else None)
                result.append(CatalogItem(
                    category=CATEGORY,
                    item=str(row.get("item", "")).strip(),
                    price=price,
                    unit=str(row.get("price_unit", "грн")).strip(),
                    source_name=str(row.get("source_name", "")).strip() or None,
                    source_url=str(row.get("source_url", "")).strip() or None,
                    collected_at=str(row.get("collected_at", "")).strip() or None,
                    package_size=pkg_size,
                    package_unit=pkg_unit,
                ))
            except Exception:
                continue
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"[{CATEGORY}] load_items failed: {e}")
    return result
