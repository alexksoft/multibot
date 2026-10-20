# wallpaper_glue.py — Клей для шпалер
#
# Клей для шпалер is sold per PACKET.
# The rule gives us how many PACKETS we need.
# We round UP to whole packets.

import logging
import math

logger = logging.getLogger(__name__)

CATEGORY = "Клей для шпалер"


def calculate(qty_packets: float, price_per_packet: float) -> dict:
    if not price_per_packet or price_per_packet <= 0:
        return {"packages": None, "qty_display": f"{qty_packets:g} пач", "total_price": None}
    packages = math.ceil(round(qty_packets, 6))
    qty_display = f"{packages} пач"
    total_price = price_per_packet * packages
    return {"packages": packages, "qty_display": qty_display, "total_price": total_price}


def can_calculate(rule_unit: str) -> bool:
    return rule_unit == "пач"


def load_items(creds_path: str, sheet_id: str) -> list:
    """Read the Клей для шпалер worksheet and return CatalogItem objects."""
    from src.multibot.config.sections import CatalogItem
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
