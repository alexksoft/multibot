# underlay.py — Підкладка
#
# Підкладка is sold in rolls. Price can be per M² or per roll.
# The rule gives us total M² needed.

import logging
import math

logger = logging.getLogger(__name__)

CATEGORY = "Підкладка"


def calculate(qty_m2: float, price_per_unit: float, price_unit: str) -> dict:
    qty_display = f"{qty_m2:g} м²"
    if "м²" in price_unit or "m2" in price_unit.lower():
        total_price = price_per_unit * qty_m2
    else:
        total_price = None  # price per roll, roll m² unknown
    return {"packages": None, "qty_display": qty_display, "total_price": total_price}


def can_calculate(rule_unit: str) -> bool:
    return rule_unit == "м²"


def load_items(creds_path: str, sheet_id: str) -> list:
    """Read the Підкладка worksheet and return CatalogItem objects."""
    from ....config.sections import CatalogItem
    import gspread
    result = []
    try:
        gc = gspread.service_account(filename=creds_path)
        ws = gc.open_by_key(sheet_id).worksheet(CATEGORY)
        for row_idx, row in enumerate(ws.get_all_records(), start=2):
            active_val = str(row.get("active", "")).strip().lower()
            if active_val and active_val not in ("true", "1", "так", "yes"):
                continue
            try:
                price = float(str(row.get("price", "")).replace("\xa0", "").replace(" ", "").replace(",", "."))
                r = row.get("roll_m2", "")
                roll_m2 = float(str(r).replace("\xa0", "").replace(" ", "").replace(",", ".")) if r not in ("", None) else None
                w = row.get("weight_kg", "")
                weight_kg = float(str(w).replace("\xa0", "").replace(" ", "").replace(",", ".")) if w not in ("", None) else None
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
            except Exception as row_err:
                logger.debug(f"[{CATEGORY}] row {row_idx} skipped: {row_err}")
    except Exception as e:
        logger.warning(f"[{CATEGORY}] load_items failed: {e}")
    return result
