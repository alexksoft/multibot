# underlay.py — Підкладка
#
# Підкладка (underlay for laminate) is sold in rolls.
# The price can be per M² (грн/м²) or per roll (грн).
# The rule gives us total M² needed.
#
# Problem: same as laminate — the scraper stores the roll WEIGHT in KG,
# not the roll COVERAGE in M². So we can't calculate how many rolls to buy.
#
# What we do:
#   - Show the raw m² quantity
#   - If price is per m²: total = price × m²
#   - If price is per roll (грн): we can't calculate total without roll coverage
#
# Example (грн/м²):
#   Need 22 м², price = 96 грн/м²  →  total = 96 × 22 = 2 112 грн
#
# Example (грн per roll):
#   Need 22 м², price = 1 190 грн/roll  →  total = unknown (no roll m² in sheet)

CATEGORY = "Підкладка"


def calculate(qty_m2: float, price_per_unit: float, price_unit: str) -> dict:
    """
    Args:
        qty_m2        -- m² of underlay needed (from rule lam_sub_m2)
        price_per_unit -- price from the sheet (per m² or per roll)
        price_unit    -- "грн/м²" or "грн"

    Returns:
        packages     -- None
        qty_display  -- e.g. "22 м²"
        total_price  -- total if price is per m², else None
    """
    qty_display = f"{qty_m2:g} м²"

    if "м²" in price_unit or "m2" in price_unit.lower():
        # Price is per m² — we can calculate total directly
        total_price = price_per_unit * qty_m2
    else:
        # Price is per roll — can't calculate without knowing m² per roll
        total_price = None

    return {"packages": None, "qty_display": qty_display, "total_price": total_price}


def can_calculate(rule_unit: str) -> bool:
    return rule_unit == "м²"


def load_items(creds_path: str, sheet_id: str) -> list:
    """
    Read the Підкладка worksheet and return CatalogItem objects.
    roll_m2 = m² per roll when available. weight_kg = roll weight.
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
                r = row.get("roll_m2", "")
                roll_m2 = float(str(r).replace(",", ".")) if r not in ("", None) else None
                w = row.get("weight_kg", "")
                weight_kg = float(str(w).replace(",", ".")) if w not in ("", None) else None
                pkg_size = roll_m2 if roll_m2 else weight_kg
                pkg_unit = "м²" if roll_m2 else ("кг" if weight_kg else None)
                result.append(CatalogItem(
                    category=CATEGORY, item=str(row.get("item", "")).strip(),
                    price=price, unit=str(row.get("price_unit", "грн")).strip(),
                    source_name=str(row.get("source_name", "")).strip() or None,
                    source_url=str(row.get("source_url", "")).strip() or None,
                    collected_at=str(row.get("collected_at", "")).strip() or None,
                    package_size=pkg_size, package_unit=pkg_unit,
                ))
            except Exception:
                continue
    except Exception as e:
        import logging; logging.getLogger(__name__).warning(f"[{CATEGORY}] load_items failed: {e}")
    return result
