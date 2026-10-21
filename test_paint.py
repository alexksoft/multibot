"""
Integration test for paint.calculate
Sheet row: Емаль Farbex алкідна ПФ-115П глянець білий 0,9 кг | price=240 | weight_kg=0.9 | volume_l=None
Calculation: qty_l=12.6 л needed, package=0.9 кг, price=240 грн
Expected: ceil(12.6 / 0.9) = 14 packages, total = 14 * 240 = 3360 грн
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from multibot.core.capabilities.calculators.paint import calculate

cases = [
    {
        "desc": "volume_l known (1 л can) — should use volume_l",
        "qty_l": 12.6, "price": 135.0, "volume_l": 1.0, "pkg_size_kg": None,
        "expect_packages": 13, "expect_unit": "л",
    },
    {
        "desc": "volume_l missing, weight_kg=0.9 — should use weight_kg",
        "qty_l": 12.6, "price": 240.0, "volume_l": None, "pkg_size_kg": 0.9,
        "expect_packages": 14, "expect_unit": "кг",
    },
    {
        "desc": "volume_l missing, weight_kg=1.2 — should use weight_kg",
        "qty_l": 12.6, "price": 319.0, "volume_l": None, "pkg_size_kg": 1.2,
        "expect_packages": 11, "expect_unit": "кг",
    },
    {
        "desc": "both missing — should show raw litres, no total",
        "qty_l": 12.6, "price": 240.0, "volume_l": None, "pkg_size_kg": None,
        "expect_packages": None, "expect_unit": None,
    },
]

print(f"{'#':<3} {'Description':<50} {'packages':>8} {'qty_display':<20} {'total':>8}  {'PASS/FAIL'}")
print("-" * 110)
all_pass = True
for i, c in enumerate(cases, 1):
    result = calculate(c["qty_l"], c["price"], c["volume_l"], pkg_size_kg=c["pkg_size_kg"])
    packages = result["packages"]
    qty_display = result["qty_display"]
    total = result["total_price"]

    ok_pkg = packages == c["expect_packages"]
    ok_unit = c["expect_unit"] is None or (c["expect_unit"] in qty_display)
    passed = ok_pkg and ok_unit
    all_pass = all_pass and passed

    status = "PASS" if passed else f"FAIL (expected {c['expect_packages']} packages)"
    total_str = f"{total:.2f}" if total is not None else "None"
    print(f"{i:<3} {c['desc']:<50} {str(packages):>8} {qty_display:<20} {total_str:>8}  {status}")

print()
print("ALL PASS" if all_pass else "SOME TESTS FAILED")
