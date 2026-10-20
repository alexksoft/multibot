# grout.py — Затирка
#
# Затирка is sold in bags/packs measured in KG.
# The rule gives us total KG needed.
# We round UP to whole packs.

import logging
import math

logger = logging.getLogger(__name__)

CATEGORY = "Затирка"


def calculate(qty_kg: float, pkg_size_kg: float, price_per_pack: float) -> dict:
    if not pkg_size_kg or pkg_size_kg <= 0:
        return {"packages": None, "qty_display": f"{qty_kg:g} кг", "total_price": None}
    packages = math.ceil(round(qty_kg / pkg_size_kg, 6))
    qty_display = f"{packages} уп. × {pkg_size_kg:g} кг"
    total_price = price_per_pack * packages
    return {"packages": packages, "qty_display": qty_display, "total_price": total_price}


def can_calculate(rule_unit: str, pkg_unit: str, pkg_size) -> bool:
    return rule_unit == "кг" and pkg_unit == "кг" and bool(pkg_size and pkg_size > 0)


def load_items(creds_path: str, sheet_id: str) -> list:
    """Read the Затирка worksheet and return CatalogItem objects."""
    from ....config.sections import CatalogItem
    import gspread
    result = []
    try:
        gc = gspread.service_account(filename=creds_path)
        ws = gc.open_by_key(sheet_id).worksheet(CATEGORY)
        from ._sheets import get_rows, to_float
        for row_idx, row in enumerate(get_rows(ws), start=2):
            active_val = str(row.get("active", "")).strip().lower()
            if active_val and active_val not in ("true", "1", "так", "yes"):
                continue
            try:
                price = to_float(row.get("price"))
                weight_kg = to_float(row.get("weight_kg"))
                result.append(CatalogItem(
                    category=CATEGORY, item=str(row.get("item", "")).strip(),
                    price=price, unit=str(row.get("price_unit", "грн")).strip(),
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
