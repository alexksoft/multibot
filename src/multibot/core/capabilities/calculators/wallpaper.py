# wallpaper.py — Шпалери
#
# Шпалери are sold per ROLL. Price is per roll (грн).
# The rule gives us how many ROLLS we need.
# We round UP to whole rolls.

import logging
import math

logger = logging.getLogger(__name__)

CATEGORY = "Шпалери"


def calculate(qty_rolls: float, price_per_roll: float) -> dict:
    packages = math.ceil(round(qty_rolls, 6))
    qty_display = f"{packages} рул"
    total_price = price_per_roll * packages
    return {"packages": packages, "qty_display": qty_display, "total_price": total_price}


def can_calculate(rule_unit: str) -> bool:
    return rule_unit == "рул"


def load_items(creds_path: str, sheet_id: str) -> list:
    """Read the Шпалери worksheet and return CatalogItem objects."""
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
                roll_m2 = to_float(row.get("roll_m2"))
                result.append(CatalogItem(
                    category=CATEGORY, item=str(row.get("item", "")).strip(),
                    price=price, unit=str(row.get("price_unit", "грн")).strip(),
                    source_name=str(row.get("source_name", "")).strip() or None,
                    source_url=str(row.get("source_url", "")).strip() or None,
                    collected_at=str(row.get("collected_at", "")).strip() or None,
                    package_size=1, package_unit="рул",
                    volume_l=roll_m2,  # store roll_m2 in volume_l for dispatch
                ))
            except Exception as row_err:
                logger.debug(f"[{CATEGORY}] row {row_idx} skipped: {row_err}")
    except Exception as e:
        logger.warning(f"[{CATEGORY}] load_items failed: {e}")
    return result
