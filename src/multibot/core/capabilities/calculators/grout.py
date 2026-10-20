# grout.py — Затирка
#
# Затирка is sold in bags/packs measured in KG.
# The rule gives us total KG needed.
# We round UP to whole packs.
#
# Example:
#   Floor 4x5 = 20 м²
#   Need: 20 × 0.3 kg/m² = 6 кг
#   Pack = 2 кг  →  ceil(6 / 2) = 3 packs
#   Price = 144 грн/pack  →  total = 3 × 144 = 432 грн

import math

CATEGORY = "Затирка"


def calculate(qty_kg: float, pkg_size_kg: float, price_per_pack: float) -> dict:
    """
    Args:
        qty_kg        -- kg of grout needed (from rule grout_kg)
        pkg_size_kg   -- kg per pack (from sheet package_size)
        price_per_pack -- price of one pack in грн

    Returns:
        packages     -- number of packs to buy
        qty_display  -- e.g. "3 уп. × 2 кг"
        total_price  -- total cost in грн
    """
    packages = math.ceil(qty_kg / pkg_size_kg)
    qty_display = f"{packages} уп. × {pkg_size_kg:g} кг"
    total_price = price_per_pack * packages
    return {"packages": packages, "qty_display": qty_display, "total_price": total_price}


def can_calculate(rule_unit: str, pkg_unit: str, pkg_size) -> bool:
    return rule_unit == "кг" and pkg_unit == "кг" and pkg_size
