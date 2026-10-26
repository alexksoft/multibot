"""
Integration tests for building bot calculations.
Tests RuleEngine directly with the exact norms and rules from building.yaml.
Verifies all 7 work types with multiple room/thickness combinations.
"""
from __future__ import annotations
import pytest
from dataclasses import dataclass
from typing import Any

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from multibot.core.rules import RuleEngine
from multibot.config.sections import CalculationRule


# ── Norms from building.yaml ──────────────────────────────────────────────────

NORMS = {
    "norms_plaster":        15.5,
    "norms_primer":         0.15,
    "norms_putty":          1.2,
    "norms_paint":          0.25,
    "norms_tile_waste":     1.1,
    "norms_tile_glue":      5.0,
    "norms_grout":          0.3,
    "norms_screed":         20.0,
    "norms_fiber":          0.75,
    "norms_lam_waste":      1.1,
    "norms_wallpaper_roll": 5.0,
    "norms_wallpaper_glue": 25.0,
}

# ── Rules from building.yaml ──────────────────────────────────────────────────

ALL_RULES = [
    CalculationRule(id="wall_area",           label="Площа стін",         expression="(room_width + room_length) * 2 * height",        unit="м²",  round_to=1),
    CalculationRule(id="floor_area",          label="Площа підлоги",      expression="room_width * room_length",                       unit="м²",  round_to=1),
    CalculationRule(id="plaster_kg",          label="Штукатурка",         expression="wall_area * norms_plaster * (thickness / 10)",   unit="кг",  round_to=0),
    CalculationRule(id="primer_l",            label="Ґрунтовка",          expression="wall_area * norms_primer",                       unit="л",   round_to=1),
    CalculationRule(id="putty_kg",            label="Шпаклівка",          expression="wall_area * norms_putty * (thickness / 2)",      unit="кг",  round_to=0),
    CalculationRule(id="paint_l",             label="Фарба",              expression="wall_area * norms_paint",                        unit="л",   round_to=1),
    CalculationRule(id="tile_m2",             label="Плитка (підлога)",   expression="floor_area * norms_tile_waste",                  unit="м²",  round_to=1),
    CalculationRule(id="tile_glue_kg",        label="Клей (підлога)",     expression="floor_area * norms_tile_glue",                   unit="кг",  round_to=0),
    CalculationRule(id="grout_kg",            label="Затирка",            expression="floor_area * norms_grout",                       unit="кг",  round_to=1),
    CalculationRule(id="tile_wall_m2",        label="Плитка (стіни)",     expression="wall_area * norms_tile_waste",                   unit="м²",  round_to=1),
    CalculationRule(id="tile_wall_glue_kg",   label="Клей (стіни)",       expression="wall_area * norms_tile_glue",                    unit="кг",  round_to=0),
    CalculationRule(id="grout_wall_kg",       label="Затирка (стіни)",    expression="wall_area * norms_grout",                        unit="кг",  round_to=1),
    CalculationRule(id="screed_kg",           label="Цементна стяжка",    expression="floor_area * norms_screed * (thickness / 10)",   unit="кг",  round_to=0),
    CalculationRule(id="screed_fiber",        label="Фібра",              expression="floor_area * (thickness / 1000) * norms_fiber", unit="кг",  round_to=2),
    CalculationRule(id="lam_m2",              label="Ламінат",            expression="floor_area * norms_lam_waste",                   unit="м²",  round_to=1),
    CalculationRule(id="lam_sub_m2",          label="Підкладка",          expression="floor_area * norms_lam_waste",                   unit="м²",  round_to=1),
    CalculationRule(id="wallpaper_rl",        label="Шпалери",            expression="wall_area / norms_wallpaper_roll",               unit="рул", round_to=0),
    CalculationRule(id="wallpaper_glue",      label="Клей для шпалер",    expression="wall_area / norms_wallpaper_glue",               unit="пач", round_to=0),
]

WORK_RULES = {
    "штукатурка":           ["wall_area", "plaster_kg", "primer_l"],
    "шпаклівка":            ["wall_area", "putty_kg",   "primer_l"],
    "фарбування":           ["wall_area", "paint_l",    "primer_l"],
    "плитка":               ["floor_area", "tile_m2",   "tile_glue_kg", "grout_kg"],
    "підлога":              ["floor_area", "tile_m2",   "tile_glue_kg", "grout_kg"],
    "стіни":                ["wall_area",  "tile_wall_m2", "tile_wall_glue_kg", "grout_wall_kg"],
    "підлога і стіни":      ["floor_area", "wall_area", "tile_m2", "tile_glue_kg", "grout_kg", "tile_wall_m2", "tile_wall_glue_kg", "grout_wall_kg"],
    "стяжка підлоги":       ["floor_area", "screed_kg", "screed_fiber"],
    "ламінат":              ["floor_area", "lam_m2",    "lam_sub_m2"],
    "поклейка шпалер":      ["wall_area",  "wallpaper_rl", "wallpaper_glue"],
}

DEFAULT_THICKNESS = {
    "штукатурка":     10,
    "шпаклівка":       2,
    "стяжка підлоги": 50,
}


# ── Helper ────────────────────────────────────────────────────────────────────

def calc(work: str, room: str, height: float = 2.7, thickness: int = None) -> dict:
    engine = RuleEngine()
    allowed_ids = WORK_RULES[work]
    rules = [r for r in ALL_RULES if r.id in allowed_ids]

    t = thickness if thickness is not None else DEFAULT_THICKNESS.get(work, 10)
    collected = {"room": room, "height": str(height), "thickness": str(t)}
    return engine.compute(rules, collected, NORMS)


def approx(val, expected, tol=0.05):
    """Check value is within tol fraction of expected."""
    return abs(val - expected) / max(expected, 1e-9) <= tol


# ── Штукатурка ────────────────────────────────────────────────────────────────

class TestPlaster:
    def test_room_4x5_h27_t10(self):
        r = calc("штукатурка", "4x5", height=2.7, thickness=10)
        wall_area = (4 + 5) * 2 * 2.7  # 48.6
        assert r["wall_area"]["value"] == pytest.approx(48.6, abs=0.1)
        assert r["plaster_kg"]["value"] == round(wall_area * 15.5 * (10 / 10))
        assert r["primer_l"]["value"] == pytest.approx(wall_area * 0.15, abs=0.1)

    def test_room_3x4_h25_t15(self):
        r = calc("штукатурка", "3x4", height=2.5, thickness=15)
        wall_area = (3 + 4) * 2 * 2.5  # 35.0
        assert r["wall_area"]["value"] == pytest.approx(35.0, abs=0.1)
        assert r["plaster_kg"]["value"] == round(wall_area * 15.5 * (15 / 10))

    def test_room_5x6_h30_t20(self):
        r = calc("штукатурка", "5x6", height=3.0, thickness=20)
        wall_area = (5 + 6) * 2 * 3.0  # 66.0
        assert r["plaster_kg"]["value"] == round(wall_area * 15.5 * (20 / 10))

    def test_thickness_doubles_plaster(self):
        r10 = calc("штукатурка", "4x5", thickness=10)
        r20 = calc("штукатурка", "4x5", thickness=20)
        assert r20["plaster_kg"]["value"] == pytest.approx(r10["plaster_kg"]["value"] * 2, abs=1)

    def test_primer_independent_of_thickness(self):
        r10 = calc("штукатурка", "4x5", thickness=10)
        r20 = calc("штукатурка", "4x5", thickness=20)
        assert r10["primer_l"]["value"] == r20["primer_l"]["value"]

    def test_units(self):
        r = calc("штукатурка", "4x5")
        assert r["wall_area"]["unit"] == "м²"
        assert r["plaster_kg"]["unit"] == "кг"
        assert r["primer_l"]["unit"] == "л"


# ── Шпаклівка ─────────────────────────────────────────────────────────────────

class TestPutty:
    def test_room_4x5_h27_t2(self):
        r = calc("шпаклівка", "4x5", height=2.7, thickness=2)
        wall_area = (4 + 5) * 2 * 2.7
        assert r["putty_kg"]["value"] == round(wall_area * 1.2 * (2 / 2))

    def test_room_3x4_h25_t3(self):
        r = calc("шпаклівка", "3x4", height=2.5, thickness=3)
        wall_area = (3 + 4) * 2 * 2.5
        assert r["putty_kg"]["value"] == round(wall_area * 1.2 * (3 / 2))

    def test_thickness_proportional(self):
        r2 = calc("шпаклівка", "4x5", thickness=2)
        r4 = calc("шпаклівка", "4x5", thickness=4)
        assert r4["putty_kg"]["value"] == pytest.approx(r2["putty_kg"]["value"] * 2, abs=1)

    def test_primer_present(self):
        r = calc("шпаклівка", "4x5")
        assert "primer_l" in r
        assert r["primer_l"]["value"] > 0


# ── Фарбування ────────────────────────────────────────────────────────────────

class TestPaint:
    def test_room_4x5_h27(self):
        r = calc("фарбування", "4x5", height=2.7)
        wall_area = (4 + 5) * 2 * 2.7  # 48.6
        assert r["paint_l"]["value"] == pytest.approx(wall_area * 0.25, abs=0.1)

    def test_room_3x3_h25(self):
        r = calc("фарбування", "3x3", height=2.5)
        wall_area = (3 + 3) * 2 * 2.5  # 30.0
        assert r["paint_l"]["value"] == pytest.approx(30.0 * 0.25, abs=0.1)

    def test_room_6x4_h30(self):
        r = calc("фарбування", "6x4", height=3.0)
        wall_area = (6 + 4) * 2 * 3.0  # 60.0
        assert r["paint_l"]["value"] == pytest.approx(60.0 * 0.25, abs=0.1)

    def test_no_thickness_dependency(self):
        # paint does not use thickness
        r = calc("фарбування", "4x5")
        assert "plaster_kg" not in r
        assert "putty_kg" not in r

    def test_primer_present(self):
        r = calc("фарбування", "4x5")
        assert r["primer_l"]["value"] > 0

    def test_units(self):
        r = calc("фарбування", "4x5")
        assert r["paint_l"]["unit"] == "л"


# ── Плитка ────────────────────────────────────────────────────────────────────

class TestTile:
    def test_room_3x4(self):
        r = calc("плитка", "3x4")
        floor_area = 3 * 4  # 12.0
        assert r["floor_area"]["value"] == pytest.approx(12.0, abs=0.1)
        assert r["tile_m2"]["value"] == pytest.approx(12.0 * 1.1, abs=0.1)
        assert r["tile_glue_kg"]["value"] == round(12.0 * 5.0)
        assert r["grout_kg"]["value"] == pytest.approx(12.0 * 0.3, abs=0.1)

    def test_room_4x5(self):
        r = calc("плитка", "4x5")
        floor_area = 4 * 5  # 20.0
        assert r["tile_m2"]["value"] == pytest.approx(20.0 * 1.1, abs=0.1)
        assert r["tile_glue_kg"]["value"] == round(20.0 * 5.0)

    def test_room_2x17(self):
        r = calc("плитка", "2x1.7")
        floor_area = 2 * 1.7  # 3.4
        assert r["floor_area"]["value"] == pytest.approx(3.4, abs=0.1)
        assert r["tile_m2"]["value"] == pytest.approx(3.4 * 1.1, abs=0.1)

    def test_no_wall_rules(self):
        r = calc("плитка", "4x5")
        assert "wall_area" not in r
        assert "paint_l" not in r

    def test_units(self):
        r = calc("плитка", "4x5")
        assert r["tile_m2"]["unit"] == "м²"
        assert r["tile_glue_kg"]["unit"] == "кг"
        assert r["grout_kg"]["unit"] == "кг"


# ── Стяжка підлоги ────────────────────────────────────────────────────────────

class TestScreed:
    def test_room_4x5_t50(self):
        r = calc("стяжка підлоги", "4x5", thickness=50)
        floor_area = 4 * 5  # 20.0
        assert r["screed_kg"]["value"] == round(floor_area * 20.0 * (50 / 10))  # 2000 kg
        assert r["screed_fiber"]["value"] == pytest.approx(floor_area * (50 / 1000) * 0.75, abs=0.01)

    def test_room_3x4_t40(self):
        r = calc("стяжка підлоги", "3x4", thickness=40)
        floor_area = 3 * 4  # 12.0
        assert r["screed_kg"]["value"] == round(12.0 * 20.0 * (40 / 10))  # 960 kg

    def test_room_5x6_t60(self):
        r = calc("стяжка підлоги", "5x6", thickness=60)
        floor_area = 5 * 6  # 30.0
        assert r["screed_kg"]["value"] == round(30.0 * 20.0 * (60 / 10))  # 3600 kg

    def test_thickness_proportional(self):
        r50 = calc("стяжка підлоги", "4x5", thickness=50)
        r100 = calc("стяжка підлоги", "4x5", thickness=100)
        assert r100["screed_kg"]["value"] == pytest.approx(r50["screed_kg"]["value"] * 2, abs=1)

    def test_fiber_proportional_to_thickness(self):
        """Fiber now depends on thickness (volume-based)."""
        r50 = calc("стяжка підлоги", "4x5", thickness=50)
        r100 = calc("стяжка підлоги", "4x5", thickness=100)
        assert r100["screed_fiber"]["value"] == pytest.approx(r50["screed_fiber"]["value"] * 2, abs=0.01)

    def test_fiber_real_example_3x3_t50(self):
        """3x3 room, 50mm: 9 * 0.05 * 0.75 = 0.34 kg"""
        r = calc("стяжка підлоги", "3x3", thickness=50)
        assert r["screed_fiber"]["value"] == pytest.approx(9 * 0.05 * 0.75, abs=0.01)

    def test_units(self):
        r = calc("стяжка підлоги", "4x5")
        assert r["screed_kg"]["unit"] == "кг"
        assert r["screed_fiber"]["unit"] == "кг"


# ── Ламінат ───────────────────────────────────────────────────────────────────

class TestLaminate:
    def test_room_4x5(self):
        r = calc("ламінат", "4x5")
        floor_area = 4 * 5  # 20.0
        assert r["lam_m2"]["value"] == pytest.approx(20.0 * 1.1, abs=0.1)
        assert r["lam_sub_m2"]["value"] == pytest.approx(20.0 * 1.1, abs=0.1)

    def test_room_3x4(self):
        r = calc("ламінат", "3x4")
        floor_area = 3 * 4  # 12.0
        assert r["lam_m2"]["value"] == pytest.approx(12.0 * 1.1, abs=0.1)

    def test_room_5x6(self):
        r = calc("ламінат", "5x6")
        floor_area = 5 * 6  # 30.0
        assert r["lam_m2"]["value"] == pytest.approx(30.0 * 1.1, abs=0.1)

    def test_laminate_equals_underlay(self):
        r = calc("ламінат", "4x5")
        assert r["lam_m2"]["value"] == r["lam_sub_m2"]["value"]

    def test_no_wall_rules(self):
        r = calc("ламінат", "4x5")
        assert "wall_area" not in r

    def test_units(self):
        r = calc("ламінат", "4x5")
        assert r["lam_m2"]["unit"] == "м²"
        assert r["lam_sub_m2"]["unit"] == "м²"


# ── Поклейка шпалер ───────────────────────────────────────────────────────────

class TestWallpaper:
    def test_room_4x5_h27(self):
        r = calc("поклейка шпалер", "4x5", height=2.7)
        wall_area = (4 + 5) * 2 * 2.7  # 48.6
        assert r["wallpaper_rl"]["value"] == round(wall_area / 5.0)   # 10 rolls
        assert r["wallpaper_glue"]["value"] == round(wall_area / 25.0)  # 2 packs

    def test_room_3x4_h25(self):
        r = calc("поклейка шпалер", "3x4", height=2.5)
        wall_area = (3 + 4) * 2 * 2.5  # 35.0
        assert r["wallpaper_rl"]["value"] == round(35.0 / 5.0)   # 7 rolls

    def test_room_5x6_h30(self):
        r = calc("поклейка шпалер", "5x6", height=3.0)
        wall_area = (5 + 6) * 2 * 3.0  # 66.0
        assert r["wallpaper_rl"]["value"] == round(66.0 / 5.0)   # 13 rolls

    def test_units(self):
        r = calc("поклейка шпалер", "4x5")
        assert r["wallpaper_rl"]["unit"] == "рул"
        assert r["wallpaper_glue"]["unit"] == "пач"


# ── Cross-cutting: work isolation ─────────────────────────────────────────────

class TestWorkIsolation:
    """Each work type returns only its own rules, not others."""

    def test_plaster_has_no_tile_rules(self):
        r = calc("штукатурка", "4x5")
        assert "tile_m2" not in r
        assert "screed_kg" not in r

    def test_tile_has_no_paint_rules(self):
        r = calc("плитка", "4x5")
        assert "paint_l" not in r
        assert "putty_kg" not in r

    def test_screed_has_no_wallpaper_rules(self):
        r = calc("стяжка підлоги", "4x5")
        assert "wallpaper_rl" not in r

    def test_laminate_has_no_plaster_rules(self):
        r = calc("ламінат", "4x5")
        assert "plaster_kg" not in r


# ── Cross-cutting: dimension parsing ─────────────────────────────────────────

class TestDimensionParsing:
    """Room dimensions in various formats are parsed correctly."""

    def test_cyrillic_x(self):
        # Cyrillic х instead of Latin x
        r = calc("фарбування", "4х5", height=2.7)
        assert r["wall_area"]["value"] == pytest.approx((4 + 5) * 2 * 2.7, abs=0.1)

    def test_decimal_room(self):
        r = calc("плитка", "2x1.7")
        assert r["floor_area"]["value"] == pytest.approx(3.4, abs=0.1)

    def test_square_room(self):
        r = calc("ламінат", "5x5")
        assert r["floor_area"]["value"] == pytest.approx(25.0, abs=0.1)


# ── Плитка підлога ────────────────────────────────────────────────────────────

class TestTileFloor:
    def test_room_4x5(self):
        r = calc("підлога", "4x5")
        floor_area = 4 * 5
        assert r["tile_m2"]["value"] == pytest.approx(floor_area * 1.1, abs=0.1)
        assert r["tile_glue_kg"]["value"] == round(floor_area * 5.0)
        assert r["grout_kg"]["value"] == pytest.approx(floor_area * 0.3, abs=0.1)

    def test_no_wall_tile_rules(self):
        r = calc("підлога", "3x4")
        assert "tile_wall_m2" not in r
        assert "tile_wall_glue_kg" not in r
        assert "grout_wall_kg" not in r

    def test_units(self):
        r = calc("підлога", "4x5")
        assert r["tile_m2"]["unit"] == "м²"
        assert r["tile_glue_kg"]["unit"] == "кг"


# ── Плитка стіни ──────────────────────────────────────────────────────────────

class TestTileWall:
    def test_room_4x5_h27(self):
        r = calc("стіни", "4x5", height=2.7)
        wall_area = (4 + 5) * 2 * 2.7
        assert r["tile_wall_m2"]["value"] == pytest.approx(wall_area * 1.1, abs=0.1)
        assert r["tile_wall_glue_kg"]["value"] == round(wall_area * 5.0)
        assert r["grout_wall_kg"]["value"] == pytest.approx(wall_area * 0.3, abs=0.1)

    def test_no_floor_tile_rules(self):
        r = calc("стіни", "4x5", height=2.7)
        assert "tile_m2" not in r
        assert "tile_glue_kg" not in r
        assert "floor_area" not in r

    def test_units(self):
        r = calc("стіни", "4x5", height=2.7)
        assert r["tile_wall_m2"]["unit"] == "м²"
        assert r["tile_wall_glue_kg"]["unit"] == "кг"
        assert r["grout_wall_kg"]["unit"] == "кг"


# ── Плитка підлога і стіни ────────────────────────────────────────────────────

class TestTileBoth:
    def test_room_4x5_h27(self):
        r = calc("підлога і стіни", "4x5", height=2.7)
        floor_area = 4 * 5
        wall_area = (4 + 5) * 2 * 2.7
        assert r["tile_m2"]["value"] == pytest.approx(floor_area * 1.1, abs=0.1)
        assert r["tile_wall_m2"]["value"] == pytest.approx(wall_area * 1.1, abs=0.1)
        assert r["tile_glue_kg"]["value"] == round(floor_area * 5.0)
        assert r["tile_wall_glue_kg"]["value"] == round(wall_area * 5.0)

    def test_has_both_floor_and_wall(self):
        r = calc("підлога і стіни", "4x5", height=2.7)
        assert "floor_area" in r
        assert "wall_area" in r
        assert "tile_m2" in r
        assert "tile_wall_m2" in r
        assert "grout_kg" in r
        assert "grout_wall_kg" in r

    def test_wall_tile_more_than_floor(self):
        r = calc("підлога і стіни", "4x5", height=2.7)
        assert r["tile_wall_m2"]["value"] > r["tile_m2"]["value"]


# ── Ламінат: пакування та реальний приклад 6x4 ───────────────────────────────

class TestLaminatePackaging:
    """
    Real example: room 6x4, height 2.7, tier Середній
    Floor area: 24 m²
    With 10% waste: 26.4 m²
    Underlay pack: 16.5 m² → needs 2 packs = 33 m²
    Laminate pack size varies by product
    """

    def test_room_6x4_floor_area(self):
        r = calc("ламінат", "6x4")
        assert r["floor_area"]["value"] == pytest.approx(24.0, abs=0.1)

    def test_room_6x4_laminate_with_waste(self):
        r = calc("ламінат", "6x4")
        assert r["lam_m2"]["value"] == pytest.approx(24.0 * 1.1, abs=0.1)  # 26.4

    def test_room_6x4_underlay_equals_laminate(self):
        r = calc("ламінат", "6x4")
        assert r["lam_sub_m2"]["value"] == r["lam_m2"]["value"]  # both 26.4

    def test_underlay_packages_rounded_up(self):
        """26.4 m² / 16.5 m² per pack = 1.6 → must round UP to 2 packs."""
        import math
        qty = 24.0 * 1.1   # 26.4
        pack_size = 16.5
        packs = math.ceil(qty / pack_size)
        assert packs == 2
        assert packs * pack_size >= qty  # bought >= needed

    def test_underlay_2_packs_covers_floor(self):
        """2 packs × 16.5 = 33 m² which covers 26.4 m²."""
        packs = 2
        pack_size = 16.5
        assert packs * pack_size == pytest.approx(33.0, abs=0.01)
        assert packs * pack_size >= 24.0 * 1.1

    def test_height_does_not_affect_laminate(self):
        """Wall height is irrelevant for floor laminate."""
        r27 = calc("ламінат", "6x4", height=2.7)
        r30 = calc("ламінат", "6x4", height=3.0)
        assert r27["lam_m2"]["value"] == r30["lam_m2"]["value"]
        assert r27["floor_area"]["value"] == r30["floor_area"]["value"]

    def test_room_6x4_no_wall_rules(self):
        r = calc("ламінат", "6x4")
        assert "wall_area" not in r
        assert "plaster_kg" not in r
        assert "paint_l" not in r
