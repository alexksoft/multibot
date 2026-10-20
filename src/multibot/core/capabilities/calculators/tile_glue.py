# tile_glue.py — Клей (для плитки)
#
# Клей для плитки is sold in bags measured in KG.
# The rule gives us total KG needed.
# We round UP to whole bags.
#
# Example:
#   Floor 4x5 = 20 м²
#   Need: 20 × 5 kg/m² = 100 кг
#   Bag = 25 кг  →  ceil(100 / 25) = 4 bags
#   Price = 458 грн/bag  →  total = 4 × 458 = 1 832 грн

import math

CATEGORY = "Клей"


def calculate(qty_kg: float, pkg_size_kg: float, price_per_bag: float) -> dict:
    """
    Args:
        qty_kg       -- kg of tile glue needed (from rule tile_glue_kg)
        pkg_size_kg  -- kg per bag (from sheet package_size)
        price_per_bag -- price of one bag in грн

    Returns:
        packages     -- number of bags to buy
        qty_display  -- e.g. "4 уп. × 25 кг"
        total_price  -- total cost in грн
    """
    packages = math.ceil(qty_kg / pkg_size_kg)
    qty_display = f"{packages} уп. × {pkg_size_kg:g} кг"
    total_price = price_per_bag * packages
    return {"packages": packages, "qty_display": qty_display, "total_price": total_price}


def can_calculate(rule_unit: str, pkg_unit: str, pkg_size) -> bool:
    return rule_unit == "кг" and pkg_unit == "кг" and pkg_size
