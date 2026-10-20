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
    packages = math.ceil(qty_packets)
    qty_display = f"{packages} пач"
    total_price = price_per_packet * packages
    return {"packages": packages, "qty_display": qty_display, "total_price": total_price}


def can_calculate(rule_unit: str) -> bool:
    return rule_unit == "пач"
