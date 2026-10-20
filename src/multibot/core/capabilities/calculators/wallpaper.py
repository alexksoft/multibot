# wallpaper.py — Шпалери
#
# Шпалери are sold per ROLL.
# The rule gives us how many ROLLS we need (already calculated from wall area).
# Each item in the shop IS one roll — price is per roll.
# We round UP to whole rolls.
#
# Example:
#   Wall area = 48.6 м²
#   Need: 48.6 / 5 m²/roll = 9.72  →  ceil = 10 rolls
#   Price = 207 грн/roll  →  total = 10 × 207 = 2 070 грн

import math

CATEGORY = "Шпалери"


def calculate(qty_rolls: float, price_per_roll: float) -> dict:
    """
    Args:
        qty_rolls     -- number of rolls needed (from rule wallpaper_rl)
        price_per_roll -- price of one roll in грн

    Returns:
        packages     -- number of rolls to buy (rounded up)
        qty_display  -- e.g. "10 рул"
        total_price  -- total cost in грн
    """
    # The rule already rounds up, but ceil again just to be safe
    packages = math.ceil(qty_rolls)
    qty_display = f"{packages} рул"
    total_price = price_per_roll * packages
    return {"packages": packages, "qty_display": qty_display, "total_price": total_price}


def can_calculate(rule_unit: str) -> bool:
    return rule_unit == "рул"


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
