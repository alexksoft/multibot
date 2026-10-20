# plaster.py — Штукатурка
#
# Штукатурка is sold in bags measured in KG.
# The rule gives us total KG needed for the walls.
# We can't buy half a bag, so we always round UP.
#
# Example:
#   Room 4x5, height 2.7 → wall area = 48.6 м²
#   Need: 48.6 × 8.5 kg/m² = 413 кг
#   Bag = 25 кг  →  ceil(413 / 25) = 17 bags
#   Price = 211 грн/bag  →  total = 17 × 211 = 3 587 грн

import math

# This is the category name exactly as it appears in the Google Sheet
CATEGORY = "Штукатурка"


def calculate(qty_kg: float, pkg_size_kg: float, price_per_bag: float) -> dict:
    """
    Args:
        qty_kg       -- kg of plaster needed (from rule plaster_kg)
        pkg_size_kg  -- kg per bag (from sheet package_size, e.g. 25)
        price_per_bag -- price of one bag in грн (from sheet price)

    Returns:
        packages     -- number of bags to buy
        qty_display  -- e.g. "17 уп. × 25 кг"
        total_price  -- total cost in грн
    """
    packages = math.ceil(qty_kg / pkg_size_kg)
    qty_display = f"{packages} уп. × {pkg_size_kg:g} кг"
    total_price = price_per_bag * packages
    return {"packages": packages, "qty_display": qty_display, "total_price": total_price}


def can_calculate(rule_unit: str, pkg_unit: str, pkg_size) -> bool:
    return rule_unit == "кг" and pkg_unit == "кг" and pkg_size
