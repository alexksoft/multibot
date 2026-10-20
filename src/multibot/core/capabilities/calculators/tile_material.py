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
