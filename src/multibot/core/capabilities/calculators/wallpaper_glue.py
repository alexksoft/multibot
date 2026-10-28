# wallpaper_glue.py — Клей для шпалер
#
# Клей для шпалер is sold per PACKET.
# The rule gives us how many PACKETS we need.
# We round UP to whole packets.

import logging
import math

logger = logging.getLogger(__name__)

CATEGORY = "Клей для шпалер"


def calculate(qty_m2: float, price_per_packet: float, volume_l: float = None, coverage_m2: float = None) -> dict:
    if not price_per_packet or price_per_packet <= 0:
        return {"packages": None, "qty_display": f"{qty_m2:g} м²", "total_price": None}
    coverage = coverage_m2 if coverage_m2 and coverage_m2 > 0 else 10.0
    packages = math.ceil(round(qty_m2 / coverage * 1.1, 6))
    qty_display = f"{packages} пач"
    total_price = price_per_packet * packages
    return {"packages": packages, "qty_display": qty_display, "total_price": total_price}


def can_calculate(rule_unit: str) -> bool:
    return rule_unit in ("пач", "л", "м²")


def load_items(creds_path: str, sheet_id: str) -> list:
    """Read the Клей для шпалер worksheet and return CatalogItem objects."""
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
                coverage_m2 = to_float(row.get("coverage_m2"))
                result.append(CatalogItem(
                    category=CATEGORY, item=str(row.get("item", "")).strip(),
                    price=price, unit=str(row.get("price_unit", "грн")).strip(),
                    source_name=str(row.get("source_name", "")).strip() or None,
                    source_url=str(row.get("source_url", "")).strip() or None,
                    collected_at=str(row.get("collected_at", "")).strip() or None,
                    package_size=coverage_m2, package_unit="м²" if coverage_m2 else None,
                    volume_l=volume_l,
                ))
            except Exception as row_err:
                logger.debug(f"[{CATEGORY}] row {row_idx} skipped: {row_err}")
    except Exception as e:
        logger.warning(f"[{CATEGORY}] load_items failed: {e}")
    return result
