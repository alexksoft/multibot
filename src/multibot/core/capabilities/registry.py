from __future__ import annotations
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from ...config.sections import Capabilities
from ..knowledge import KnowledgeBase
from ..rules import RuleEngine

logger = logging.getLogger(__name__)


@dataclass
class CapabilityResult:
    success: bool
    text: str
    data: dict = field(default_factory=dict)
    error: str = ""


@runtime_checkable
class Capability(Protocol):
    name: str

    async def run(self, knowledge: KnowledgeBase, rules: RuleEngine,
                  collected: dict, params: dict) -> CapabilityResult: ...


class CalculateMaterials:
    name = "calculate_materials"

    async def run(self, knowledge: KnowledgeBase, rules: RuleEngine,
                  collected: dict, params: dict) -> CapabilityResult:
        all_rules = params.get("_rules", [])
        work_rules_map: dict = params.get("_work_rules", {})
        norms = knowledge.get_norms()
        # Filter rules by work type if mapping exists
        work = collected.get("work", "").lower()
        if work and work_rules_map:
            allowed_ids = work_rules_map.get(work, [])
            if allowed_ids:
                all_rules = [r for r in all_rules if r.id in allowed_ids]
        results = rules.compute(all_rules, collected, norms)
        if not results:
            return CapabilityResult(False, "Не вдалося розрахувати матеріали. Перевірте введені дані.", error="no results")
        lines = [f"• {v['label']}: {v['value']} {v['unit']}" for v in results.values()]
        return CapabilityResult(True, "📐 Розрахунок матеріалів:\n" + "\n".join(lines), data=results)


class SearchProducts:
    name = "search_products"

    async def run(self, knowledge: KnowledgeBase, rules: RuleEngine,
                  collected: dict, params: dict) -> CapabilityResult:
        category = collected.get("work") or collected.get("category") or params.get("category", "")
        if not category:
            cats = await knowledge.list_categories()
            if cats:
                return CapabilityResult(True, "Доступні категорії:\n" + "\n".join(f"• {c}" for c in cats))
            return CapabilityResult(False, "Каталог порожній або недоступний.", error="empty")

        items = await knowledge.list_items(category)
        if not items:
            cats = await knowledge.list_categories()
            alt = "\n".join(f"• {c}" for c in cats[:5]) if cats else ""
            msg = f"Позицій у категорії «{category}» не знайдено."
            if alt:
                msg += f"\nДоступні категорії:\n{alt}"
            return CapabilityResult(False, msg, error="not_found")

        lines = []
        for i in items:
            price_str = knowledge.format_price(i)
            lines.append(f"• {i.item}: {price_str}")
        return CapabilityResult(True, f"🛒 {category}:\n" + "\n".join(lines), data={"items": [i.model_dump() for i in items]})


class ShoppingList:
    name = "shopping_list"

    async def run(self, knowledge: KnowledgeBase, rules: RuleEngine,
                  collected: dict, params: dict) -> CapabilityResult:
        calc_data = collected.get("_calc_results", {})
        lines = ["📋 Список покупок:"]
        for rule_id, info in calc_data.items():
            category = info.get("label", rule_id)
            items = await knowledge.list_items(category)
            qty = info.get("value", "?")
            unit = info.get("unit", "")
            if items:
                item = items[0]
                price_str = knowledge.format_price(item)
                lines.append(f"• {category}: {qty} {unit} — {price_str}")
            else:
                lines.append(f"• {category}: {qty} {unit} (ціна не знайдена в каталозі)")
        if len(lines) == 1:
            return CapabilityResult(False, "Спочатку виконайте розрахунок матеріалів.", error="no_calc")
        return CapabilityResult(True, "\n".join(lines))


class Checklist:
    name = "checklist"

    async def run(self, knowledge: KnowledgeBase, rules: RuleEngine,
                  collected: dict, params: dict) -> CapabilityResult:
        template = params.get("template", "general")
        items_map = {
            "general": ["Виміряйте приміщення", "Підготуйте поверхні", "Придбайте матеріали", "Підготуйте інструменти"],
            "measurement": ["Виміряйте ширину", "Виміряйте довжину", "Виміряйте висоту", "Запишіть розміри"],
            "beauty": ["Визначте бажаний результат", "Підготуйте приклади (фото)", "Запишіть питання до майстра"],
            "auto": ["Опишіть симптоми", "Перевірте рівень масла", "Перевірте тиск у шинах", "Підготуйте документи"],
        }
        items = items_map.get(template, items_map["general"])
        text = "✅ Чекліст:\n" + "\n".join(f"☐ {i}" for i in items)
        return CapabilityResult(True, text)


class QuestionsForPro:
    name = "questions_for_pro"

    async def run(self, knowledge: KnowledgeBase, rules: RuleEngine,
                  collected: dict, params: dict) -> CapabilityResult:
        industry = params.get("industry", "")
        questions_map = {
            "будівництво": ["Яка технологія підходить для моїх умов?", "Скільки часу займе робота?", "Які матеріали ви рекомендуєте?", "Чи є гарантія на роботу?"],
            "меблі": ["Які матеріали найдовговічніші?", "Чи можна замовити нестандартний розмір?", "Скільки часу займе виготовлення?"],
            "авто": ["Що саме потрібно замінити?", "Які деталі використовуєте (оригінал/аналог)?", "Яка гарантія на роботу?"],
            "вікна": ["Яка комплектація підходить для мого клімату?", "Скільки часу займе монтаж?", "Чи є гарантія?"],
            "б'юті": ["Яка процедура підходить для мого типу волосся/шкіри?", "Скільки часу займе процедура?", "Як доглядати після?"],
        }
        questions = []
        for key, qs in questions_map.items():
            if key in industry.lower():
                questions = qs
                break
        if not questions:
            questions = ["Що саме входить у послугу?", "Скільки часу займе?", "Яка гарантія?", "Що потрібно підготувати?"]
        text = "❓ Питання до фахівця:\n" + "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
        return CapabilityResult(True, text)


class CompareOptions:
    name = "compare_options"

    async def run(self, knowledge: KnowledgeBase, rules: RuleEngine,
                  collected: dict, params: dict) -> CapabilityResult:
        category = collected.get("work") or collected.get("category") or params.get("category", "")
        if not category:
            return CapabilityResult(False, "Вкажіть категорію для порівняння.", error="no_category")
        items = await knowledge.list_items(category)
        if len(items) < 2:
            return CapabilityResult(False, f"Недостатньо варіантів у «{category}» для порівняння.", error="few_items")
        lines = [f"⚖️ Порівняння варіантів «{category}»:"]
        for i in items[:5]:
            price_str = knowledge.format_price(i)
            attrs = ", ".join(f"{k}: {v}" for k, v in i.attributes.items()) if i.attributes else ""
            line = f"• {i.item}: {price_str}"
            if attrs:
                line += f" ({attrs})"
            lines.append(line)
        return CapabilityResult(True, "\n".join(lines))


class PrepareRequest:
    name = "prepare_request"

    async def run(self, knowledge: KnowledgeBase, rules: RuleEngine,
                  collected: dict, params: dict) -> CapabilityResult:
        lines = ["📄 Ваш готовий запит:"]
        for key, val in collected.items():
            if not key.startswith("_"):
                lines.append(f"• {key}: {val}")
        calc = collected.get("_calc_results", {})
        if calc:
            lines.append("\n📐 Розрахунок:")
            for info in calc.values():
                lines.append(f"• {info['label']}: {info['value']} {info['unit']}")
        lines.append("\n💡 Передайте цей запит будь-якому обраному постачальнику.")
        return CapabilityResult(True, "\n".join(lines), data={"collected": collected})


_ALL_CAPABILITIES: list[Capability] = [
    CalculateMaterials(), SearchProducts(), ShoppingList(),
    Checklist(), QuestionsForPro(), CompareOptions(), PrepareRequest(),
]


class CapabilityRegistry:
    def __init__(self, config: Capabilities, knowledge: KnowledgeBase,
                 rules: RuleEngine, knowledge_config=None):
        self._enabled = {c.name: c for c in config.enabled}
        self._caps = {c.name: c for c in _ALL_CAPABILITIES}
        self._knowledge = knowledge
        self._rules = rules
        self._knowledge_config = knowledge_config  # for passing calc rules

    def is_allowed(self, name: str) -> bool:
        return name in self._enabled

    async def run(self, name: str, collected: dict) -> CapabilityResult:
        if not self.is_allowed(name):
            return CapabilityResult(False, f"Функція '{name}' недоступна.", error="not_allowed")
        cap = self._caps.get(name)
        if not cap:
            return CapabilityResult(False, f"Функція '{name}' не реалізована.", error="not_implemented")
        params = dict(self._enabled[name].params)
        if name == "calculate_materials" and self._knowledge_config:
            params["_rules"] = self._knowledge_config.calculation_rules
            params["_work_rules"] = self._knowledge_config.work_rules
        try:
            return await cap.run(self._knowledge, self._rules, collected, params)
        except Exception as e:
            logger.error(f"[capability] '{name}' error: {e}")
            return CapabilityResult(False, "Помилка виконання функції.", error=str(e))
