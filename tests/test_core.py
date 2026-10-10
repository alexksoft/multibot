"""Tests for config sections, RuleEngine, KnowledgeBase, and storage."""
import pytest
from pydantic import ValidationError

from src.multibot.config.sections import (
    AssistantProfile, BotConfig, CatalogItem, Capabilities, CapabilityRef,
    ConversationFlows, Flow, Integrations, KnowledgeData, AIPolicy, Step,
)
from src.multibot.core.rules import RuleEngine, safe_eval
from src.multibot.core.storage import InMemoryStorage, DialogState


# ── Config validation ─────────────────────────────────────────────────────────

def test_assistant_profile_valid():
    p = AssistantProfile(assistant_role="Test", industry="test", target_user="users")
    assert p.disclaimer != ""
    assert p.version == 1


def test_catalog_item_price_requires_source():
    with pytest.raises(ValidationError):
        CatalogItem(category="X", item="Y", price=100.0)  # no source_name


def test_catalog_item_price_with_source():
    item = CatalogItem(category="X", item="Y", price=100.0, source_name="Shop", source_url="https://x.ua", collected_at="2026-01")
    assert item.price == 100.0


def test_catalog_item_no_price_no_source_ok():
    item = CatalogItem(category="X", item="Y")
    assert item.price is None


def test_choice_step_requires_options():
    with pytest.raises(ValidationError):
        Step(id="s1", kind="question", question_type="choice")  # no options


def test_flow_start_must_exist():
    with pytest.raises(ValidationError):
        Flow(id="f1", title="T", start="missing", steps=[
            Step(id="s1", kind="message", text="hi")
        ])


def test_capabilities_is_enabled():
    caps = Capabilities(enabled=[CapabilityRef(name="calculate_materials")])
    assert caps.is_enabled("calculate_materials")
    assert not caps.is_enabled("checklist")


# ── RuleEngine ────────────────────────────────────────────────────────────────

def test_safe_eval_basic():
    assert safe_eval("2 + 3 * 4", {}) == 14.0


def test_safe_eval_variables():
    assert safe_eval("a * b", {"a": 3.0, "b": 4.0}) == 12.0


def test_safe_eval_forbidden():
    with pytest.raises(ValueError):
        safe_eval("__import__('os')", {})


def test_safe_eval_unknown_var():
    with pytest.raises(ValueError):
        safe_eval("unknown_var + 1", {})


def test_rule_engine_dimension():
    from src.multibot.config.sections import CalculationRule
    engine = RuleEngine()
    rules = [
        CalculationRule(id="wall_area", label="Площа стін",
                        expression="(room_width + room_length) * 2 * height",
                        unit="м²", round_to=1),
    ]
    result = engine.compute(rules, {"room": "4x5", "height": "2.7"}, {})
    assert "wall_area" in result
    assert result["wall_area"]["value"] == pytest.approx(48.6, 0.01)


def test_rule_engine_skips_bad_rule():
    from src.multibot.config.sections import CalculationRule
    engine = RuleEngine()
    rules = [
        CalculationRule(id="bad", label="Bad", expression="nonexistent_var * 2"),
        CalculationRule(id="good", label="Good", expression="2 + 2"),
    ]
    result = engine.compute(rules, {}, {})
    assert "bad" not in result
    assert "good" in result


# ── Storage ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_inmemory_state_roundtrip():
    storage = InMemoryStorage()
    state = DialogState("bot1", 123, "flow1", "step1", {"key": "val"})
    await storage.save_state(state)
    loaded = await storage.get_state("bot1", 123)
    assert loaded is not None
    assert loaded.flow_id == "flow1"
    assert loaded.collected["key"] == "val"


@pytest.mark.asyncio
async def test_inmemory_clear_state():
    storage = InMemoryStorage()
    state = DialogState("bot1", 123, "flow1", "step1")
    await storage.save_state(state)
    await storage.clear_state("bot1", 123)
    assert await storage.get_state("bot1", 123) is None


@pytest.mark.asyncio
async def test_inmemory_counters():
    storage = InMemoryStorage()
    await storage.incr_counter("bot1", "results")
    await storage.incr_counter("bot1", "results")
    stats = await storage.stats("bot1")
    assert stats["results"] == 2


# ── Smoke: all 5 bot configs validate ────────────────────────────────────────

import yaml
from pathlib import Path

@pytest.mark.parametrize("yaml_file", list(Path("bots").glob("*.yaml")))
def test_bot_config_validates(yaml_file):
    raw = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
    cfg = BotConfig.model_validate(raw)
    assert cfg.name
    assert cfg.assistant_profile.disclaimer
