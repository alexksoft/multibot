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
