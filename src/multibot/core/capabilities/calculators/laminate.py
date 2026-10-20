# laminate.py — Ламінат
#
# Ламінат is sold in boxes. Price is per M² (грн/м²).
# The rule gives us total M² needed (includes 10% waste factor).
# Box m² coverage not always available — show raw m², total = price × m².

import logging

logger = logging.getLogger(__name__)

CATEGORY = "Ламінат"


def calculate(qty_m2: float, price_per_m2: float) -> dict:
    qty_display = f"{qty_m2:g} м²"
    total_price = price_per_m2 * qty_m2
    return {"packages": None, "qty_display": qty_display, "total_price": total_price}


def can_calculate(rule_unit: str, price_unit: str) -> bool:
    return rule_unit == "м²" and ("м²" in price_unit or "m2" in price_unit.lower())


def load_items(creds_path: str, sheet_id: str) -> list:
    """Read the Ламінат worksheet and return CatalogItem objects."""
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
                w = row.get("weight_kg", "")
                weight_kg = float(str(w).replace("\xa0", "").replace(" ", "").replace(",", ".")) if w not in ("", None) else None
                result.append(CatalogItem(
                    category=CATEGORY, item=str(row.get("item", "")).strip(),
                    price=price, unit=str(row.get("price_unit", "грн/м²")).strip(),
                    source_name=str(row.get("source_name", "")).strip() or None,
                    source_url=str(row.get("source_url", "")).strip() or None,
                    collected_at=str(row.get("collected_at", "")).strip() or None,
                    package_size=weight_kg, package_unit="кг" if weight_kg else None,
                ))
            except Exception as row_err:
                logger.debug(f"[{CATEGORY}] row {row_idx} skipped: {row_err}")
    except Exception as e:
        logger.warning(f"[{CATEGORY}] load_items failed: {e}")
    return result
