# tile_material.py — Плитка
#
# Плитка is sold in boxes. Each box covers a fixed area in M².
# The price is per M² (грн/м²).
# The rule gives us total M² needed (already includes 10% waste factor).
#
# How to calculate:
#   - Divide total m² by m² per box → round UP to whole boxes
#   - Total cost = price_per_m² × total_m²  (NOT × number of boxes!)
#     Because the price is already "per square metre".
#
# Example:
#   Floor 4x5 = 20 м², waste factor 1.1 → need 22 м²
#   Box = 1.44 м²  →  ceil(22 / 1.44) = ceil(15.28) = 16 boxes
#   Price = 944 грн/м²  →  total = 944 × 22 = 20 768 грн

import math

CATEGORY = "Плитка"


def calculate(qty_m2: float, pkg_size_m2: float, price_per_m2: float) -> dict:
    """
    Args:
        qty_m2       -- m² of tile needed (from rule tile_m2, includes waste)
        pkg_size_m2  -- m² per box (from sheet package_size)
        price_per_m2 -- price per m² in грн (from sheet price)

    Returns:
        packages     -- number of boxes to buy
        qty_display  -- e.g. "16 уп. × 1.44 м²"
        total_price  -- total cost in грн (price_per_m² × total_m²)
    """
    packages = math.ceil(qty_m2 / pkg_size_m2)
    qty_display = f"{packages} уп. × {pkg_size_m2:g} м²"
    # Price is per m², so multiply by m² — NOT by number of boxes
    total_price = price_per_m2 * qty_m2
    return {"packages": packages, "qty_display": qty_display, "total_price": total_price}


def can_calculate(rule_unit: str, pkg_unit: str, price_unit: str, pkg_size) -> bool:
    return (
        rule_unit == "м²"
        and pkg_unit == "м²"
        and ("м²" in price_unit or "m2" in price_unit.lower())
        and pkg_size
    )


def load_items(creds_path: str, sheet_id: str) -> list:
    """
    Read the Плитка worksheet and return CatalogItem objects.
    box_m2 = m² per box. Price is грн/м².
    """
    from src.multibot.config.sections import CatalogItem
    import gspread
    result = []
    try:
        gc = gspread.service_account(filename=creds_path)
        ws = gc.open_by_key(sheet_id).worksheet(CATEGORY)
        for row in ws.get_all_records():
            if str(row.get("active", "true")).lower() not in ("true", "1", "так"):
                continue
            try:
                price = float(str(row.get("price", "")).replace(",", "."))
                b = row.get("box_m2", "")
                box_m2 = float(str(b).replace(",", ".")) if b not in ("", None) else None
                result.append(CatalogItem(
                    category=CATEGORY, item=str(row.get("item", "")).strip(),
                    price=price, unit=str(row.get("price_unit", "грн/м²")).strip(),
                    source_name=str(row.get("source_name", "")).strip() or None,
                    source_url=str(row.get("source_url", "")).strip() or None,
                    collected_at=str(row.get("collected_at", "")).strip() or None,
                    package_size=box_m2, package_unit="м²" if box_m2 else None,
                ))
            except Exception:
                continue
    except Exception as e:
        import logging; logging.getLogger(__name__).warning(f"[{CATEGORY}] load_items failed: {e}")
    return result
