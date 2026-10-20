# putty.py — Шпаклівка
#
# Шпаклівка is sold in bags measured in KG.
# The rule gives us total KG needed for the walls.
# We round UP to whole bags.
#
# Example:
#   Wall area = 48.6 м²
#   Need: 48.6 × 1.2 kg/m² = 58 кг
#   Bag = 25 кг  →  ceil(58 / 25) = 3 bags
#   Price = 375 грн/bag  →  total = 3 × 375 = 1 125 грн

import math

CATEGORY = "Шпаклівка"


def calculate(qty_kg: float, pkg_size_kg: float, price_per_bag: float) -> dict:
    """
    Args:
        qty_kg       -- kg of putty needed (from rule putty_kg)
        pkg_size_kg  -- kg per bag (from sheet package_size)
        price_per_bag -- price of one bag in грн

    Returns:
        packages     -- number of bags to buy
        qty_display  -- e.g. "3 уп. × 25 кг"
        total_price  -- total cost in грн
    """
    if not pkg_size_kg or pkg_size_kg <= 0:
        return {"packages": None, "qty_display": f"{qty_kg:g} кг", "total_price": None}
    qty_rounded = round(qty_kg, 6)
    packages = math.ceil(qty_rounded / pkg_size_kg)
    qty_display = f"{packages} уп. × {pkg_size_kg:g} кг"
    total_price = price_per_bag * packages
    return {"packages": packages, "qty_display": qty_display, "total_price": total_price}


def can_calculate(rule_unit: str, pkg_unit: str, pkg_size) -> bool:
    return rule_unit == "кг" and pkg_unit == "кг" and pkg_size


def load_items(creds_path: str, sheet_id: str) -> list:
    """Read the Шпаклівка worksheet and return CatalogItem objects."""
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
                w = row.get("weight_kg", "")
                weight_kg = float(str(w).replace(",", ".")) if w not in ("", None) else None
                result.append(CatalogItem(
                    category=CATEGORY, item=str(row.get("item", "")).strip(),
                    price=price, unit=str(row.get("price_unit", "грн")).strip(),
                    source_name=str(row.get("source_name", "")).strip() or None,
                    source_url=str(row.get("source_url", "")).strip() or None,
                    collected_at=str(row.get("collected_at", "")).strip() or None,
                    package_size=weight_kg, package_unit="кг" if weight_kg else None,
                ))
            except Exception:
                continue
    except Exception as e:
        import logging; logging.getLogger(__name__).warning(f"[{CATEGORY}] load_items failed: {e}")
    return result