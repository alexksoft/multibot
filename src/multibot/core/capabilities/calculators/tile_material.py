# tile_material.py — Плитка
#
# Плитка is sold in boxes. Price is per M² (грн/м²).
# The rule gives us total M² needed (includes 10% waste factor).
# Total cost = price_per_m² × total_m² (NOT × number of boxes).

import logging
import math

logger = logging.getLogger(__name__)

CATEGORY = "Плитка"


def calculate(qty_m2: float, pkg_size_m2: float, price_per_m2: float) -> dict:
    if not pkg_size_m2 or pkg_size_m2 <= 0:
        return {"packages": None, "qty_display": f"{qty_m2:g} м²", "total_price": round(price_per_m2 * qty_m2, 2)}
    packages = math.ceil(round(qty_m2 / pkg_size_m2, 6))
    price_per_pkg = round(price_per_m2 * pkg_size_m2, 2)
    total_price = packages * price_per_pkg
    qty_display = f"{packages} уп. × {pkg_size_m2:g} м² ({price_per_pkg:,.0f} грн/уп.)"
    return {"packages": packages, "qty_display": qty_display, "total_price": total_price, "unit_price": price_per_pkg}


def can_calculate(rule_unit: str, pkg_unit: str, price_unit: str, pkg_size) -> bool:
    return (
        rule_unit == "м²"
        and pkg_unit == "м²"
        and ("м²" in price_unit or "m2" in price_unit.lower())
        and bool(pkg_size and pkg_size > 0)
    )


def load_items(creds_path: str, sheet_id: str) -> list:
    """Read the Плитка worksheet and return CatalogItem objects."""
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
                box_m2 = to_float(row.get("box_m2"))
                result.append(CatalogItem(
                    category=CATEGORY, item=str(row.get("item", "")).strip(),
                    price=price, unit=str(row.get("price_unit", "грн/м²")).strip(),
                    source_name=str(row.get("source_name", "")).strip() or None,
                    source_url=str(row.get("source_url", "")).strip() or None,
                    collected_at=str(row.get("collected_at", "")).strip() or None,
                    package_size=box_m2, package_unit="м²" if box_m2 else None,
                ))
            except Exception as row_err:
                logger.debug(f"[{CATEGORY}] row {row_idx} skipped: {row_err}")
    except Exception as e:
        logger.warning(f"[{CATEGORY}] load_items failed: {e}")
    return result
