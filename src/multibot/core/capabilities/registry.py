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
    document: bytes | None = None
    document_name: str = "result.pdf"


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
        skip = ShoppingList._SKIP_RULES
        lines = [f"• {v['label']}: {v['value']} {v['unit']}" for k, v in results.items()
                 if k not in skip and not k.endswith("_area") and not k.endswith("_perimeter")]
        return CapabilityResult(True, "\ud83d\udcd0 \u0420\u043e\u0437\u0440\u0430\u0445\u0443\u043d\u043e\u043a \u043c\u0430\u0442\u0435\u0440\u0456\u0430\u043b\u0456\u0432:\n" + "\n".join(lines), data=results)


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

    # Rule IDs that are intermediate calculations, not purchasable materials
    _SKIP_RULES = {"wall_area", "floor_area", "ceiling_area", "perimeter"}

    async def run(self, knowledge: KnowledgeBase, rules: RuleEngine,
                  collected: dict, params: dict) -> CapabilityResult:
        calc_data = collected.get("_calc_results", {})
        lines = ["Список покупок:"]
        shopping_results = {}
        for rule_id, info in calc_data.items():
            if rule_id in self._SKIP_RULES or rule_id.endswith("_area") or rule_id.endswith("_perimeter"):
                continue
            category = info.get("label", rule_id)
            items = await knowledge.list_items(category)
            qty = info.get("value", "?")
            unit = info.get("unit", "")
            if items:
                item = items[0]
                price_str = knowledge.format_price(item)
                url = item.source_url or ""
                name = item.item[:60]
                if url:
                    linked = f'<a href="{url}">{name}</a>'
                else:
                    linked = name
                lines.append(f"• {category}: {qty} {unit}\n  {linked} — {price_str}")
                shopping_results[rule_id] = {
                    "label": category, "qty": qty, "unit": unit,
                    "price_str": price_str,
                    "item_name": item.item,
                    "source_url": url,
                }
            else:
                lines.append(f"• {category}: {qty} {unit} (ціна не знайдена в каталозі)")
                shopping_results[rule_id] = {"label": category, "qty": qty, "unit": unit, "price_str": "—", "item_name": "", "source_url": ""}
        if len(lines) == 1:
            return CapabilityResult(False, "Спочатку виконайте розрахунок матеріалів.", error="no_calc")
        collected["_shopping_results"] = shopping_results
        return CapabilityResult(True, "\n".join(lines), data=shopping_results)


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


# Human-readable labels for collected keys
_FIELD_LABELS = {
    "work": "Вид робіт",
    "room": "Розміри кімнати",
    "height": "Висота стін (м)",
}


class PrepareRequest:
    name = "prepare_request"

    async def run(self, knowledge: KnowledgeBase, rules: RuleEngine,
                  collected: dict, params: dict) -> CapabilityResult:
        calc = collected.get("_calc_results", {})
        shopping = collected.get("_shopping_results", {})

        # Build text summary
        lines = ["📄 Ваш розрахунок матеріалів:"]
        for key, val in collected.items():
            if key.startswith("_"):
                continue
            label = _FIELD_LABELS.get(key, key)
            lines.append(f"• {label}: {val}")
        if calc:
            lines.append("\n\U0001f4d0 \u041a\u0456\u043b\u044c\u043a\u0456\u0441\u0442\u044c \u043c\u0430\u0442\u0435\u0440\u0456\u0430\u043b\u0456\u0432:")
            skip = ShoppingList._SKIP_RULES
            for rule_id, info in calc.items():
                if rule_id in skip or rule_id.endswith("_area") or rule_id.endswith("_perimeter"):
                    continue
                lines.append(f"  {info['label']}: {info['value']} {info['unit']}")
        if shopping:
            lines.append("\nЦіни з Епіцентру:")
            for entry in shopping.values():
                price = entry.get("price_str") or "ціна не знайдена"
                item_name = entry.get("item_name", "")
                url = entry.get("source_url", "")
                if item_name and url:
                    linked = f'<a href="{url}">{item_name[:60]}</a>'
                elif item_name:
                    linked = item_name[:60]
                else:
                    linked = ""
                qty_str = f"{entry.get('qty','')} {entry.get('unit','')}".strip()
                line = f"  {entry['label']}: {qty_str}"
                if linked:
                    line += f"\n  {linked} — {price}"
                else:
                    line += f" — {price}"
                lines.append(line)
        lines.append("\n💡 Ці цифри — середні по ринку. Покажіть їх будівельникам при обговоренні ціни.")
        text = "\n".join(lines)

        # Generate PDF
        pdf_bytes = _build_pdf(collected, calc, shopping)
        result = CapabilityResult(True, text, data={"collected": collected})
        result.document = pdf_bytes
        result.document_name = f"rozrakhunok_{collected.get('work', 'materialy')}.pdf"
        return result


def _build_pdf(collected: dict, calc: dict, shopping: dict) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import io, os

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
                                leftMargin=2*cm, rightMargin=2*cm,
                                topMargin=2*cm, bottomMargin=2*cm)

        # Try to register a Unicode font for Cyrillic; fall back to built-in
        font_name = "Helvetica"
        for path in ["/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",
                     "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                     "/usr/share/fonts/dejavu/DejaVuSans.ttf",
                     "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]:
            if os.path.exists(path):
                try:
                    pdfmetrics.registerFont(TTFont("CyrFont", path))
                    font_name = "CyrFont"
                except Exception:
                    pass
                break

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("title", fontName=font_name, fontSize=16,
                                     spaceAfter=12, textColor=colors.HexColor("#1a1a2e"))
        h2_style = ParagraphStyle("h2", fontName=font_name, fontSize=12,
                                  spaceBefore=12, spaceAfter=6,
                                  textColor=colors.HexColor("#16213e"))
        body_style = ParagraphStyle("body", fontName=font_name, fontSize=10, spaceAfter=4)
        note_style = ParagraphStyle("note", fontName=font_name, fontSize=9,
                                    textColor=colors.grey, spaceAfter=4)

        story = []
        story.append(Paragraph("Розрахунок матеріалів для ремонту", title_style))

        # Parameters section
        story.append(Paragraph("Параметри", h2_style))
        for key, val in collected.items():
            if not key.startswith("_"):
                label = _FIELD_LABELS.get(key, key)
                story.append(Paragraph(f"{label}: {val}", body_style))

        # Materials section
        if calc:
            story.append(Spacer(1, 0.3*cm))
            story.append(Paragraph("Кількість матеріалів", h2_style))
            table_data = [["\u041c\u0430\u0442\u0435\u0440\u0456\u0430\u043b", "\u041a\u0456\u043b\u044c\u043a\u0456\u0441\u0442\u044c", "\u041e\u0434\u0438\u043d\u0438\u0446\u044f"]]
            skip = ShoppingList._SKIP_RULES
            for rule_id, info in calc.items():
                if rule_id in skip or rule_id.endswith("_area") or rule_id.endswith("_perimeter"):
                    continue
                table_data.append([info["label"], str(info["value"]), info["unit"]])
            t = Table(table_data, colWidths=[9*cm, 4*cm, 3*cm])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f4f8")),
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9f9f9")]),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(t)

        # Prices section
        if shopping:
            story.append(Spacer(1, 0.3*cm))
            story.append(Paragraph("Ціни з Епіцентру", h2_style))
            link_style = ParagraphStyle("link", fontName=font_name, fontSize=9,
                                          textColor=colors.HexColor("#0645AD"), leading=12)
            table_data = [["Матеріал / Товар", "К-сть", "Ціна"]]
            for entry in shopping.values():
                item_name = entry.get("item_name", "")
                url = entry.get("source_url", "")
                qty_str = f"{entry.get('qty','')} {entry.get('unit','')}".strip()
                # Category label bold + item name as link below
                if item_name and url:
                    cell = Paragraph(
                        f"<b>{entry['label']}</b><br/>"
                        f'<link href="{url}" color="#0645AD">{item_name[:55]}</link>',
                        link_style
                    )
                elif item_name:
                    cell = Paragraph(f"<b>{entry['label']}</b><br/>{item_name[:55]}", link_style)
                else:
                    cell = Paragraph(f"<b>{entry['label']}</b>", link_style)
                table_data.append([cell, qty_str, entry.get("price_str") or "—"])
            t = Table(table_data, colWidths=[10*cm, 3*cm, 4*cm])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f4f8")),
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9f9f9")]),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(t)

        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph(
            "Ці цифри — середні по ринку. Покажіть їх будівельникам при обговоренні ціни.",
            note_style
        ))

        doc.build(story)
        return buf.getvalue()
    except Exception as e:
        logger.warning(f"[pdf] generation failed: {e}")
        return b""


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
