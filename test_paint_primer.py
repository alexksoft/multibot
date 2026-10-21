"""
Integration test for primer.calculate and paint.calculate

Real sheet examples:
  Primer: Feidal Streichputz UA 16 kg | price=2102.4 | weight_kg=16 | volume_l=None
    qty=8.4 л -> ceil(8.4/16)=1 package, total=1*2102.4=2102.4
  Paint:  Kolorit Legenda 9 л        | price=4440   | volume_l=9   | weight_kg=12.4
    qty=14.0 л -> ceil(14/9)=2 packages, total=2*4440=8880
  Combined total: 2102.4 + 8880 = 10982.4
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from multibot.core.capabilities.calculators.paint import calculate as paint_calc
from multibot.core.capabilities.calculators.primer import calculate as primer_calc

cases = [
    # --- PRIMER ---
    {
        "fn": primer_calc, "label": "primer",
        "desc": "volume_l=1 л can",
        "qty": 8.4, "price": 135.0, "volume_l": 1.0, "pkg_size_kg": None,
        "expect_packages": 9, "expect_unit": "л", "expect_total": 1215.0,
    },
    {
        "fn": primer_calc, "label": "primer",
        "desc": "volume_l=None, weight_kg=16 (Feidal Streichputz)",
        "qty": 8.4, "price": 2102.4, "volume_l": None, "pkg_size_kg": 16.0,
        "expect_packages": 1, "expect_unit": "кг", "expect_total": 2102.4,
    },
    {
        "fn": primer_calc, "label": "primer",
        "desc": "both missing -> raw litres",
        "qty": 8.4, "price": 135.0, "volume_l": None, "pkg_size_kg": None,
        "expect_packages": None, "expect_unit": None, "expect_total": None,
    },
    # --- PAINT ---
    {
        "fn": paint_calc, "label": "paint",
        "desc": "volume_l=9 л (Kolorit Legenda)",
        "qty": 14.0, "price": 4440.0, "volume_l": 9.0, "pkg_size_kg": 12.4,
        "expect_packages": 2, "expect_unit": "л", "expect_total": 8880.0,
    },
    {
        "fn": paint_calc, "label": "paint",
        "desc": "volume_l=None, weight_kg=0.9 (Farbex enamel)",
        "qty": 12.6, "price": 240.0, "volume_l": None, "pkg_size_kg": 0.9,
        "expect_packages": 14, "expect_unit": "кг", "expect_total": 3360.0,
    },
]

print(f"{'#':<3} {'mod':<7} {'desc':<42} {'pkg':>4} {'display':<22} {'total':>9}  result")
print("-" * 100)
all_pass = True
for i, c in enumerate(cases, 1):
    r = c["fn"](c["qty"], c["price"], c["volume_l"], pkg_size_kg=c["pkg_size_kg"])
    pkg = r["packages"]
    disp = r["qty_display"]
    total = r["total_price"]

    ok = (pkg == c["expect_packages"] and
          (c["expect_unit"] is None or c["expect_unit"] in disp) and
          (c["expect_total"] is None or (total is not None and abs(total - c["expect_total"]) < 0.01)))
    all_pass = all_pass and ok
    total_str = f"{total:.2f}" if total is not None else "None"
    print(f"{i:<3} {c['label']:<7} {c['desc']:<42} {str(pkg):>4} {disp:<22} {total_str:>9}  {'PASS' if ok else 'FAIL'}")

print()
# Combined total for the real bot scenario (primer 16kg + paint 9l)
p_primer = primer_calc(8.4, 2102.4, None, pkg_size_kg=16.0)
p_paint  = paint_calc(14.0, 4440.0, 9.0, pkg_size_kg=12.4)
combined = (p_primer["total_price"] or 0) + (p_paint["total_price"] or 0)
print(f"Combined total (primer 1x2102.4 + paint 2x4440): {combined:.2f} grn  (expected 10982.40)")
print()
print("ALL PASS" if all_pass else "SOME TESTS FAILED")
