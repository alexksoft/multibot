# paint.py — Фарба
#
# Фарба is sold in cans measured in LITRES.
# The rule gives us total LITRES needed.
#
# Problem: the scraper stores the package weight in KG (e.g. 16 кг for a 10-litre can).
# We can't divide litres by kilograms to get a package count.
#
# What we do:
#   - Show the raw litre quantity to the user
#   - Show the price of one can as a reference
#   - Skip this item in the total
#
# Example:
#   Wall area = 48.6 м²
#   Need: 48.6 × 0.25 l/m² = 12.2 л
#   Display: "12.2 л  →  Фарба Feidal Hit 10л — 1 014 грн/уп (Епіцентр)"

CATEGORY = "Фарба"


def calculate(qty_l: float, price_per_can: float) -> dict:
    """
    Args:
        qty_l        -- litres of paint needed (from rule paint_l)
        price_per_can -- price of one can in грн (shown as reference only)

    Returns:
        packages     -- None
        qty_display  -- e.g. "12.2 л"
        total_price  -- None (excluded from total)
    """
    qty_display = f"{qty_l:g} л"
    return {"packages": None, "qty_display": qty_display, "total_price": None}


def can_calculate(rule_unit: str, pkg_unit: str, pkg_size) -> bool:
    return rule_unit == "л"
