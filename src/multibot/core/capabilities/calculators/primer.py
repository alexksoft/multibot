# primer.py — Ґрунтовка
#
# Ґрунтовка is sold in cans measured in LITRES.
# The rule gives us total LITRES needed.
#
# Problem: the scraper stores the package weight in KG (e.g. 10.4 кг for a 10-litre can).
# We can't divide litres by kilograms to get a package count.
#
# What we do:
#   - Show the raw litre quantity to the user
#   - Show the price of one can as a reference
#   - Skip this item in the total (we don't know how many cans to buy)
#
# Future fix: if the scraper ever extracts "Об'єм: 10 л" from the product page
# and stores it as package_size with package_unit="л", then we can do:
#   packages = ceil(4.2 л / 10 л) = 1 can

CATEGORY = "Ґрунтовка"


def calculate(qty_l: float, price_per_can: float) -> dict:
    """
    Args:
        qty_l        -- litres of primer needed (from rule primer_l)
        price_per_can -- price of one can in грн (shown as reference only)

    Returns:
        packages     -- None (can't calculate without litre volume per can)
        qty_display  -- e.g. "4.2 л"
        total_price  -- None (excluded from total)
    """
    qty_display = f"{qty_l:g} л"
    # We can't calculate total without knowing litres per can
    return {"packages": None, "qty_display": qty_display, "total_price": None}


def can_calculate(rule_unit: str, pkg_unit: str, pkg_size) -> bool:
    # Always use this file for Ґрунтовка regardless of package info
    return rule_unit == "л"
