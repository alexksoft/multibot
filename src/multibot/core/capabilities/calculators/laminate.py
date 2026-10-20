# laminate.py — Ламінат
#
# Ламінат is sold in boxes. The price is per M² (грн/м²).
# The rule gives us total M² needed (includes 10% waste factor).
#
# Problem: the scraper stores the box WEIGHT in KG (e.g. 17.5 кг),
# not the box COVERAGE in M². So we can't calculate how many boxes to buy.
#
# What we do:
#   - Show the raw m² quantity to the user
#   - Calculate total cost as price_per_m² × total_m² — this IS correct
#     even without knowing the box count
#   - The user can then figure out box count at the shop
#
# Example:
#   Floor 4x5 = 20 м², waste 1.1 → need 22 м²
#   Price = 549 грн/м²  →  total = 549 × 22 = 12 078 грн
#   Display: "22 м²  →  Ламінат YILDIZ Stilo — 549 грн/м² (Епіцентр)"

CATEGORY = "Ламінат"


def calculate(qty_m2: float, price_per_m2: float) -> dict:
    """
    Args:
        qty_m2       -- m² of laminate needed (from rule lam_m2, includes waste)
        price_per_m2 -- price per m² in грн (from sheet price)

    Returns:
        packages     -- None (box m² coverage unknown from scraper)
        qty_display  -- e.g. "22 м²"
        total_price  -- total cost in грн (price_per_m² × m²)
    """
    qty_display = f"{qty_m2:g} м²"
    total_price = price_per_m2 * qty_m2
    return {"packages": None, "qty_display": qty_display, "total_price": total_price}


def can_calculate(rule_unit: str, price_unit: str) -> bool:
    return rule_unit == "м²" and ("м²" in price_unit or "m2" in price_unit.lower())
