# wallpaper_glue.py — Клей для шпалер
#
# Клей для шпалер is sold per PACKET.
# The rule gives us how many PACKETS we need (calculated from wall area).
# We round UP to whole packets.
#
# Example:
#   Wall area = 48.6 м²
#   Need: 48.6 / 25 m²/packet = 1.94  →  ceil = 2 packets
#   Price = 123 грн/packet  →  total = 2 × 123 = 246 грн

import math

CATEGORY = "Клей для шпалер"


def calculate(qty_packets: float, price_per_packet: float) -> dict:
    """
    Args:
        qty_packets      -- number of packets needed (from rule wallpaper_glue)
        price_per_packet -- price of one packet in грн

    Returns:
        packages     -- number of packets to buy (rounded up)
        qty_display  -- e.g. "2 пач"
        total_price  -- total cost in грн
    """
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
        for row in ws.get_all_records():
            if str(row.get("active", "true")).lower() not in ("true", "1", "так"):
                continue
            try:
                price = float(str(row.get("price", "")).replace(",", "."))
                w = row.get("weight_kg", "")
                weight_kg = float(str(w).replace(",", ".")) if w not in ("", None) else None
                result.append(CatalogItem(
                    category=CATEGORY, item=str(row.get("item", "")).strip(),
                    price=price, unit=str(row.get("price_unit", "грн")).strip(),
                    source_name=str(row.get("source_name", "")).strip() or None,
                    source_url=str(row.get("source_url", "")).strip() or None,
                    collected_at=str(row.get("collected_at", "")).strip() or None,
                    package_size=weight_kg, package_unit="кг" if weight_kg else None,
                ))
            except Exception:
                continue
    except Exception as e:
        import logging; logging.getLogger(__name__).warning(f"[{CATEGORY}] load_items failed: {e}")
    return result