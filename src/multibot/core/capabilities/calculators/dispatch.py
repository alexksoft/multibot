# dispatch.py
#
# Routes each category to its own calculator file.
# ShoppingList in registry.py calls dispatch() and gets back a unified result.
#
# To add a new category:
#   1. Create a new file in this folder (e.g. new_category.py)
#   2. Add it to the CATEGORY_MAP below

from . import (
    plaster, putty, primer, paint,
    tile_material, tile_glue, grout,
    screed, fiber,
    laminate, underlay,
    wallpaper, wallpaper_glue,
)

# Maps the category label (exactly as in Google Sheet / building.yaml rule label)
# to its calculator module
CATEGORY_MAP = {
    "Штукатурка":       plaster,
    "Шпаклівка":        putty,
    "Ґрунтовка":        primer,
    "Фарба":            paint,
    "Плитка":           tile_material,
    "Клей":             tile_glue,
    "Затирка":          grout,
    "Цементна стяжка":  screed,
    "Фібра":            fiber,
    "Ламінат":          laminate,
    "Підкладка":        underlay,
    "Шпалери":          wallpaper,
    "Клей для шпалер":  wallpaper_glue,
}


def dispatch(
    category: str,
    rule_unit: str,
    pkg_unit: str,
    price_unit: str,
    qty: float,
    pkg_size,
    unit_price: float,
    item_name: str = "",
    volume_l: float = None,
) -> dict:
    """
    Pick the right calculator for this category and return a unified result.

    Always returns:
        packages     -- int or None
        qty_display  -- str shown to the user
        total_price  -- float or None (None = excluded from total)
    """
    mod = CATEGORY_MAP.get(category)

    # --- Штукатурка / Шпаклівка / Клей / Затирка / Цементна стяжка / Фібра ---
    if mod in (plaster, putty, tile_glue, grout, screed, fiber):
        if mod.can_calculate(rule_unit, pkg_unit, pkg_size):
            return mod.calculate(qty, pkg_size, unit_price)

    # --- Ґрунтовка / Фарба ---
    elif mod in (primer, paint):
        if mod.can_calculate(rule_unit, pkg_unit, pkg_size):
            return mod.calculate(qty, unit_price, volume_l)

    # --- Плитка ---
    elif mod is tile_material:
        if mod.can_calculate(rule_unit, pkg_unit, price_unit, pkg_size):
            return mod.calculate(qty, pkg_size, unit_price)

    # --- Ламінат ---
    elif mod is laminate:
        if mod.can_calculate(rule_unit, price_unit):
            return mod.calculate(qty, unit_price)

    # --- Підкладка ---
    elif mod is underlay:
        if mod.can_calculate(rule_unit):
            return mod.calculate(qty, unit_price, price_unit)

    # --- Шпалери ---
    elif mod is wallpaper:
        if mod.can_calculate(rule_unit):
            return mod.calculate(qty, unit_price)

    # --- Клей для шпалер ---
    elif mod is wallpaper_glue:
        if mod.can_calculate(rule_unit):
            return mod.calculate(qty, unit_price)

    # Fallback: unknown category or missing package data — show raw qty
    return {
        "packages": None,
        "qty_display": f"{qty:g} {rule_unit}",
        "total_price": unit_price * qty if unit_price else None,
    }
