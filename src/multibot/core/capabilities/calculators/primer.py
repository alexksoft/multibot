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
    return rule_unit == "л"


def load_items(creds_path: str, sheet_id: str) -> list:
    """
    Read the Ґрунтовка worksheet and return CatalogItem objects.
    Reads volume_l (litres) so the calculator can use it for package count.
    """
    from src.multibot.config.sections import CatalogItem
    import gspread
    result = []
    try:
        gc = gspread.service_account(filename=creds_path)
        ws = gc.open_by_key(sheet_id).worksheet(CATEGORY)
        for row in ws.get_all_records():
            if str(row.get("active", "true")).lower() not in ("true", "1", "так"):
                continue
            try:
                price = float(str(row.get("price", "")).replace(",", "."))
                v = row.get("volume_l", "")
                volume_l = float(str(v).replace(",", ".")) if v not in ("", None) else None
                w = row.get("weight_kg", "")
                weight_kg = float(str(w).replace(",", ".")) if w not in ("", None) else None
                result.append(CatalogItem(
                    category=CATEGORY, item=str(row.get("item", "")).strip(),
                    price=price, unit=str(row.get("price_unit", "грн")).strip(),
                    source_name=str(row.get("source_name", "")).strip() or None,
                    source_url=str(row.get("source_url", "")).strip() or None,
                    collected_at=str(row.get("collected_at", "")).strip() or None,
                    package_size=weight_kg, package_unit="кг" if weight_kg else None,
                    volume_l=volume_l,
                ))
            except Exception:
                continue
    except Exception as e:
        import logging; logging.getLogger(__name__).warning(f"[{CATEGORY}] load_items failed: {e}")
    return result
