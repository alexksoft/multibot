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
    packages = math.ceil(qty_kg / pkg_size_kg)
    qty_display = f"{packages} уп. × {pkg_size_kg:g} кг"
    total_price = price_per_bag * packages
    return {"packages": packages, "qty_display": qty_display, "total_price": total_price}


def can_calculate(rule_unit: str, pkg_unit: str, pkg_size) -> bool:
    return rule_unit == "кг" and pkg_unit == "кг" and pkg_size
