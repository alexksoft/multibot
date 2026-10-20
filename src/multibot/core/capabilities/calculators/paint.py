# paint.py — Фарба
#
# Фарба is sold in cans measured in LITRES.
# The rule gives us total LITRES needed.
# We use volume_l from the sheet to calculate how many cans to buy.

import logging
import math

logger = logging.getLogger(__name__)

CATEGORY = "Фарба"


def calculate(qty_l: float, price_per_can: float, volume_l_per_can: float = None,
              pkg_unit: str = "л", pkg_size_kg: float = None) -> dict:
    logger.info(f"[paint.calculate] qty_l={qty_l} volume_l={volume_l_per_can} pkg_size_kg={pkg_size_kg}")
    if volume_l_per_can and volume_l_per_can > 0:
        packages = math.ceil(round(qty_l / volume_l_per_can, 6))
        qty_display = f"{packages} уп. × {volume_l_per_can:g} л"
        total_price = price_per_can * packages
    else:
        packages = None
        qty_display = f"{qty_l:g} л"
        total_price = None
    logger.info(f"[paint.calculate] result: {qty_display}")
    return {"packages": packages, "qty_display": qty_display, "total_price": total_price}


def can_calculate(rule_unit: str, pkg_unit: str, pkg_size) -> bool:
    return rule_unit == "л"


def load_items(creds_path: str, sheet_id: str) -> list:
    """Read the Фарба worksheet and return CatalogItem objects."""
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
                volume_l = to_float(row.get("volume_l"))
                weight_kg = to_float(row.get("weight_kg"))
                result.append(CatalogItem(
                    category=CATEGORY, item=str(row.get("item", "")).strip(),
                    price=price, unit=str(row.get("price_unit", "грн")).strip(),
                    source_name=str(row.get("source_name", "")).strip() or None,
                    source_url=str(row.get("source_url", "")).strip() or None,
                    collected_at=str(row.get("collected_at", "")).strip() or None,
                    package_size=weight_kg, package_unit="кг" if weight_kg else None,
                    volume_l=volume_l,
                ))
            except Exception as row_err:
                logger.debug(f"[{CATEGORY}] row {row_idx} skipped: {row_err}")
    except Exception as e:
        logger.warning(f"[{CATEGORY}] load_items failed: {e}")
    return result
