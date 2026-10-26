from __future__ import annotations
import logging
import re as _re
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

    # default thickness (mm) per work type — used when user is not asked
    _DEFAULT_THICKNESS = {
        "штукатурка": 10,
        "шпаклівка":  2,
        "стяжка підлоги": 50,
    }

    async def run(self, knowledge: KnowledgeBase, rules: RuleEngine,
                  collected: dict, params: dict) -> CapabilityResult:
        all_rules = params.get("_rules", [])
        work_rules_map: dict = params.get("_work_rules", {})
        norms = knowledge.get_norms()
        work = collected.get("work", "").lower()
        tile_surface = collected.get("tile_surface", "").lower()

        # For tile, use tile_surface to pick the right rule set
        lookup_key = work
        if work == "плитка" and tile_surface:
            lookup_key = tile_surface

        if lookup_key and work_rules_map:
            allowed_ids = work_rules_map.get(lookup_key, work_rules_map.get(work, []))
            if allowed_ids:
                all_rules = [r for r in all_rules if r.id in allowed_ids]
        # inject default thickness if not already set
        if "thickness" not in collected and work in self._DEFAULT_THICKNESS:
            collected["thickness"] = str(self._DEFAULT_THICKNESS[work])
        results = rules.compute(all_rules, collected, norms)
        if not results:
            return CapabilityResult(False, "Не вдалося розрахувати матеріали. Перевірте введені дані.", error="no results")
        # Store data silently — PrepareRequest will render everything
        return CapabilityResult(True, "", data=results)


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

    _SKIP_RULES = {"wall_area", "floor_area", "ceiling_area", "perimeter"}

    async def run(self, knowledge: KnowledgeBase, rules: RuleEngine,
                  collected: dict, params: dict) -> CapabilityResult:
        calc_data = collected.get("_calc_results", {})
        shopping_results = {}
        total = 0.0

        for rule_id, info in calc_data.items():
            if rule_id in self._SKIP_RULES or rule_id.endswith("_area") or rule_id.endswith("_perimeter"):
                continue
            category = info.get("label", rule_id)
            rule_unit = info.get("unit", "")
            try:
                qty = float(str(info.get("value", 0)).replace(",", "."))
            except (ValueError, TypeError):
                qty = 0.0

            tier = collected.get("price_tier", "")
            catalog_category = category.split(" (")[0].strip()
            item = await knowledge.tiered_item(catalog_category, tier)
            logger.info(f"[shopping] category={category!r} rule_unit={rule_unit!r} qty={qty} item={'found: '+item.item[:30] if item else 'NOT FOUND'}")
            if not item:
                shopping_results[rule_id] = {
                    "label": category, "qty": qty, "unit": rule_unit,
                    "qty_display": f"{qty} {rule_unit}",
                    "price_str": "—", "item_name": "", "source_url": "",
                    "source_name": "", "collected_at": "",
                }
                continue

            from .calculators.dispatch import dispatch
            pkg_size = item.package_size
            pkg_unit = item.package_unit or ""
            price_unit = item.unit or ""
            unit_price = 0.0
            m = _re.match(r"([\d\s]+(?:[.,]\d+)?)", (knowledge.format_price(item) or "").replace("\xa0", " "))
            if m:
                try:
                    unit_price = float(m.group(1).replace(" ", "").replace(",", "."))
                except ValueError:
                    pass

            calc = dispatch(catalog_category, rule_unit, pkg_unit, price_unit, qty, pkg_size, unit_price, volume_l=item.volume_l)
            logger.info(f"[shopping] dispatch result: category={category!r} pkg_size={pkg_size} pkg_unit={pkg_unit!r} unit_price={unit_price} -> {calc}")
            packages = calc["packages"]
            qty_display = calc["qty_display"]
            if calc["total_price"] is not None:
                total += calc["total_price"]
            # dispatch may return a corrected unit_price (e.g. tile: per-package not per-m2)
            if "unit_price" in calc:
                unit_price = calc["unit_price"]

            price_str = knowledge.format_price(item)
            shopping_results[rule_id] = {
                "label": category, "qty": qty, "unit": rule_unit,
                "qty_display": qty_display,
                "packages": packages,
                "pkg_size": pkg_size, "pkg_unit": pkg_unit,
                "price_str": price_str,
                "item_name": item.item,
                "source_url": item.source_url or "",
                "source_name": item.source_name or "",
                "collected_at": item.collected_at or "",
                "unit_price": unit_price,
            }

        if not shopping_results:
            return CapabilityResult(False, "Спочатку виконайте розрахунок матеріалів.", error="no_calc")

        if total > 0:
            total_str = f"{int(total):,}".replace(",", " ")
            shopping_results["_total"] = total_str

        collected["_shopping_results"] = shopping_results
        # Store data silently — PrepareRequest will render everything
        return CapabilityResult(True, "", data=shopping_results)


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


_TIER_LABELS = {
    "економ":   "💰 Економ",
    "середній": "⭐ Середній",
    "преміум":  "💎 Преміум",
}

_FIELD_LABELS = {
    "work":   "Вид робіт",
    "room":   "Розміри кімнати",
    "height": "Висота стін (м)",
}


class PrepareRequest:
    name = "prepare_request"

    async def run(self, knowledge: KnowledgeBase, rules: RuleEngine,
                  collected: dict, params: dict) -> CapabilityResult:
        calc     = collected.get("_calc_results", {})
        shopping = collected.get("_shopping_results", {})

        work   = collected.get("work", "")
        room   = collected.get("room", "")
        height = collected.get("height", "")
        tier   = (collected.get("price_tier") or "").lower()
        tier_label = _TIER_LABELS.get(tier, tier.capitalize())
        thickness  = collected.get("thickness", "")
        _THICKNESS_LABEL = {
            "штукатурка": "шар штукатурки",
            "шпаклівка":  "шар шпаклівки",
            "стяжка підлоги": "товщина стяжки",
        }
        thickness_label = _THICKNESS_LABEL.get((work or "").lower(), "")

        lines = []

        # ── Header ──────────────────────────────────────────────────────────────────
        lines.append(f"🎨 {work}")
        _floor_only = (work.lower() in ("ламінат", "стяжка підлоги") or (work.lower() == "плитка" and (collected.get("tile_surface") or "").lower() == "підлога"))
        if room and height and not _floor_only:
            lines.append(f"📏 Кімната {room} м, висота стін {height} м")
        elif room and _floor_only:
            lines.append(f"📏 Кімната {room} м")
        if thickness and thickness_label:
            lines.append(f"📏 {thickness_label}: {thickness} мм")
        if tier_label:
            lines.append(f"Клас: {tier_label}")

        # ── Quantities ───────────────────────────────────────────────────────
        if calc:
            lines.append("")
            lines.append("📐 Скільки потрібно")
            skip = ShoppingList._SKIP_RULES
            for rule_id, info in calc.items():
                if rule_id in skip or rule_id.endswith("_area") or rule_id.endswith("_perimeter"):
                    continue
                lines.append(f"• {info['label']}: {info['value']} {info['unit']}")

        # ── Shopping list ────────────────────────────────────────────────────
        if shopping:
            lines.append("")
            lines.append("🛒 Що купити")
            sources, dates = set(), set()
            items_list = [(k, v) for k, v in shopping.items() if k != "_total" and isinstance(v, dict)]
            for idx, (key, entry) in enumerate(items_list, 1):
                item_name   = entry.get("item_name", "")
                url         = entry.get("source_url", "")
                qty_display = entry.get("qty_display", "")
                price_str   = entry.get("price_str") or "—"
                packages    = entry.get("packages")
                unit_price  = entry.get("unit_price", 0.0)
                if entry.get("source_name"):
                    sources.add(entry["source_name"])
                if entry.get("collected_at"):
                    dates.add(entry["collected_at"])

                linked = f'<a href="{url}">{item_name}</a>' if url else item_name
                lines.append("")
                lines.append(f"{idx}️⃣ {entry['label']}")
                if linked:
                    lines.append(linked)
                if packages and unit_price:
                    row = f"{packages} уп. × {unit_price:,.2f} грн = {packages * unit_price:,.2f} грн"
                    lines.append(row.replace(",", "\u00a0"))
                else:
                    lines.append(f"{qty_display} — {price_str}")

        # ── Total ────────────────────────────────────────────────────────────
        RESERVE_PCT = params.get("reserve_pct", 10)
        total_str = shopping.get("_total", "")
        if total_str:
            try:
                total_val = float(total_str.replace("\u00a0", "").replace(" ", ""))
                reserve_val = total_val * RESERVE_PCT / 100
                grand_val = total_val + reserve_val
                total_fmt   = f"{int(total_val):,}".replace(",", "\u00a0")
                reserve_fmt = f"{int(reserve_val):,}".replace(",", "\u00a0")
                grand_fmt   = f"{int(grand_val):,}".replace(",", "\u00a0")
                lines.append("")
                lines.append(f"\U0001f9fe \u0422\u043e\u0432\u0430\u0440\u0438: {total_fmt} \u0433\u0440\u043d")
                lines.append(f"\u2795 \u0417\u0430\u043f\u0430\u0441 {RESERVE_PCT}% (\u0434\u043e\u0441\u0442\u0430\u0432\u043a\u0430, \u0434\u0440\u0456\u0431\u043d\u0438\u0446\u0456, \u043d\u0435\u043f\u0435\u0440\u0435\u0434\u0431\u0430\u0447\u0435\u043d\u0435): {reserve_fmt} \u0433\u0440\u043d")
                lines.append("")
                lines.append(f"\U0001f4b0 \u0420\u0430\u0437\u043e\u043c \u2248 {grand_fmt} \u0433\u0440\u043d")
            except ValueError:
                lines.append("")
                lines.append(f"\U0001f4b0 \u0420\u0430\u0437\u043e\u043c \u2248 {total_str} \u0433\u0440\u043d")

        # ── Source & note ────────────────────────────────────────────────────
        if shopping:
            src_str  = ", ".join(sorted(sources))
            date_str = ", ".join(sorted(dates))
            if src_str:
                lines.append(f"🏪 Ціни: {src_str}{', ' + date_str if date_str else ''}")

        lines.append("")
        lines.append("💡 Це середні ринкові ціни. Покажіть їх будівельникам при обговоренні ціни.")
        text = "\n".join(lines)

        # Generate PDF
        pdf_bytes = _build_pdf(collected, calc, shopping)
        result = CapabilityResult(True, text, data={"collected": collected})
        result.document = pdf_bytes
        result.document_name = f"rozrakhunok_{collected.get('work', 'materialy')}.pdf"
        return result


def _build_pdf(collected: dict, calc: dict, shopping: dict) -> bytes:
    RESERVE_PCT = 10
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import io, os, math

        buf = io.BytesIO()
        from reportlab.lib.pagesizes import landscape
        doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                                leftMargin=2*cm, rightMargin=2*cm,
                                topMargin=2*cm, bottomMargin=2*cm)

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

        def P(text, **kw):
            style = ParagraphStyle("s", fontName=font_name, fontSize=10, **kw)
            return Paragraph(text, style)

        def fmt(val):
            return f"{val:,.0f}".replace(",", "\u00a0")

        title_s  = ParagraphStyle("t",  fontName=font_name, fontSize=15, spaceAfter=4,  textColor=colors.HexColor("#1a1a2e"))
        sub_s    = ParagraphStyle("sb", fontName=font_name, fontSize=10, spaceAfter=10, textColor=colors.HexColor("#444444"))
        h2_s     = ParagraphStyle("h2", fontName=font_name, fontSize=11, spaceBefore=10, spaceAfter=4, textColor=colors.HexColor("#16213e"))
        body_s   = ParagraphStyle("b",  fontName=font_name, fontSize=10, spaceAfter=3)
        link_s   = ParagraphStyle("l",  fontName=font_name, fontSize=9,  leading=13, textColor=colors.HexColor("#0645AD"))
        note_s   = ParagraphStyle("n",  fontName=font_name, fontSize=9,  textColor=colors.grey)
        right_s  = ParagraphStyle("r",  fontName=font_name, fontSize=10, alignment=2)
        bold_r_s = ParagraphStyle("br", fontName=font_name, fontSize=10, alignment=2)

        work   = collected.get("work", "")
        room   = collected.get("room", "")
        height = collected.get("height", "")
        tier   = (collected.get("price_tier") or "").lower()
        tier_labels = {"економ": "Економ", "середній": "Середній", "преміум": "Преміум"}
        tier_label = tier_labels.get(tier, tier.capitalize())

        thickness_pdf = collected.get("thickness", "")
        _THICK_PDF = {
            "штукатурка": "шар штукатурки",
            "шпаклівка":  "шар шпаклівки",
            "стяжка підлоги": "товщина стяжки",
        }
        thick_lbl_pdf = _THICK_PDF.get((work or "").lower(), "")
        thickness_pdf = collected.get("thickness", "")
        _THICK_PDF = {
            "штукатурка": "шар штукатурки",
            "шпаклівка":  "шар шпаклівки",
            "стяжка підлоги": "товщина стяжки",
        }
        thick_lbl_pdf = _THICK_PDF.get((work or "").lower(), "")
        subtitle_parts = [p for p in [
            work,
            f"Кімната {room}\u00a0м" if room else "",
            f"висота стін {height}\u00a0м" if height else "",
            f"{thick_lbl_pdf} {thickness_pdf} мм" if thickness_pdf and thick_lbl_pdf else "",
            f"Клас: {tier_label}" if tier_label else "",
        ] if p]

        story = []
        story.append(Paragraph("Розрахунок матеріалів для ремонту", title_s))
        story.append(Paragraph(" \u00b7 ".join(subtitle_parts), sub_s))

        # ── Quantities ───────────────────────────────────────────────────────
        if calc:
            story.append(Paragraph("Скільки потрібно", h2_s))
            skip = ShoppingList._SKIP_RULES
            qty_rows = []
            for rule_id, info in calc.items():
                if rule_id in skip or rule_id.endswith("_area") or rule_id.endswith("_perimeter"):
                    continue
                qty_rows.append([info["label"], f"{info['value']} {info['unit']}"])
            if qty_rows:
                t = Table(qty_rows, colWidths=[10*cm, 6*cm])
                t.setStyle(TableStyle([
                    ("FONTNAME",     (0, 0), (-1, -1), font_name),
                    ("FONTSIZE",     (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
                    ("TOPPADDING",   (0, 0), (-1, -1), 3),
                    ("LINEBELOW",    (0, 0), (-1, -1), 0.3, colors.lightgrey),
                ]))
                story.append(t)

        # ── Shopping table ───────────────────────────────────────────────────
        if shopping:
            story.append(Spacer(1, 0.3*cm))
            story.append(Paragraph("Список покупок", h2_s))

            HDR_BG  = colors.HexColor("#dce8f0")
            ROW_BG1 = colors.white
            ROW_BG2 = colors.HexColor("#f5f9fc")
            NOTE_FG = colors.HexColor("#666666")

            header = [
                Paragraph("<b>Товар</b>",        link_s),
                Paragraph("<b>Кількість</b>",   link_s),
                Paragraph("<b>Ціна за уп.</b>", link_s),
                Paragraph("<b>Сума</b>",         link_s),
            ]
            table_data = [header]
            table_styles = [
                ("BACKGROUND",   (0, 0), (-1, 0),  HDR_BG),
                ("FONTNAME",     (0, 0), (-1, -1), font_name),
                ("FONTSIZE",     (0, 0), (-1, -1), 9),
                ("GRID",         (0, 0), (-1, -1), 0.4, colors.HexColor("#c0d0dc")),
                ("TOPPADDING",   (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
                ("VALIGN",       (0, 0), (-1, -1), "TOP"),
            ]

            items_list = [(k, v) for k, v in shopping.items() if k != "_total" and isinstance(v, dict)]
            sources, dates = set(), set()

            for row_idx, (key, entry) in enumerate(items_list, 1):
                item_name  = entry.get("item_name", "")
                url        = entry.get("source_url", "")
                qty_display = entry.get("qty_display", "")
                unit_price = entry.get("unit_price", 0.0)
                packages   = entry.get("packages")
                pkg_size   = entry.get("pkg_size")
                pkg_unit   = entry.get("pkg_unit", "")
                qty_needed = entry.get("qty", 0.0)
                if entry.get("source_name"): sources.add(entry["source_name"])
                if entry.get("collected_at"): dates.add(entry["collected_at"])

                # item cell: bold label + linked name
                if item_name and url:
                    item_cell = Paragraph(
                        f"<b>{entry['label']}</b><br/>"
                        f'<link href="{url}" color="#0645AD">{item_name}</link>',
                        link_s
                    )
                elif item_name:
                    item_cell = Paragraph(f"<b>{entry['label']}</b><br/>{item_name}", link_s)
                else:
                    item_cell = Paragraph(f"<b>{entry['label']}</b>", link_s)

                price_cell = Paragraph(f"{fmt(unit_price)} грн" if unit_price else "—", body_s)

                if packages and unit_price:
                    row_total = packages * unit_price
                    sum_cell  = Paragraph(f"<b>{fmt(row_total)} грн</b>", body_s)
                else:
                    row_total = None
                    sum_cell  = Paragraph("—", body_s)

                bg = ROW_BG1 if row_idx % 2 == 1 else ROW_BG2
                data_row_idx = row_idx  # 1-based, header is 0
                table_styles.append(("BACKGROUND", (0, data_row_idx), (-1, data_row_idx), bg))

                table_data.append([item_cell, qty_display, price_cell, sum_cell])

                # remainder row
                if packages and pkg_size and qty_needed:
                    bought = packages * pkg_size
                    remainder = bought - qty_needed
                    if remainder > 0.01:
                        rem_text = f"Залишиться \u2248 {remainder:g} {pkg_unit or entry.get('unit','')}"
                        rem_row_idx = len(table_data)
                        table_data.append([
                            Paragraph(f"<i>{rem_text}</i>",
                                      ParagraphStyle("rem", fontName=font_name, fontSize=8, textColor=NOTE_FG)),
                            "", "", ""
                        ])
                        table_styles.append(("BACKGROUND", (0, rem_row_idx), (-1, rem_row_idx), bg))
                        table_styles.append(("SPAN", (0, rem_row_idx), (-1, rem_row_idx)))

            t = Table(table_data, colWidths=[11*cm, 5*cm])
            t.setStyle(TableStyle(table_styles))
            story.append(t)

            # ── Totals block ─────────────────────────────────────────────────
            total_str = shopping.get("_total", "")
            if total_str:
                try:
                    total_val   = float(total_str.replace("\u00a0", "").replace(" ", ""))
                    reserve_val = total_val * RESERVE_PCT / 100
                    grand_val   = total_val + reserve_val
                    totals_data = [
                        [Paragraph("Товари:",                                                    body_s), Paragraph(f"{fmt(total_val)} грн",   body_s)],
                        [Paragraph(f"Запас {RESERVE_PCT}% (доставка, дрібниці):",  body_s), Paragraph(f"{fmt(reserve_val)} грн", body_s)],
                        [Paragraph("<b>РАЗОМ \u2248</b>",                                          link_s), Paragraph(f"<b>{fmt(grand_val)} грн</b>",  link_s)],
                    ]
                    t2 = Table(totals_data, colWidths=[8*cm, 3*cm, 2.5*cm, 2.5*cm])
                    t2.setStyle(TableStyle([
                        ("FONTNAME",     (0, 0), (-1, -1), font_name),
                        ("FONTSIZE",     (0, 0), (-1, -1), 10),
                        ("TOPPADDING",   (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
                        ("ALIGN",        (1, 0), (1, -1),  "RIGHT"),
                        ("LINEABOVE",    (0, 0), (-1, 0),  0.5, colors.HexColor("#aaaaaa")),
                        ("LINEABOVE",    (0, 2), (-1, 2),  1.0, colors.HexColor("#333333")),
                        ("BACKGROUND",   (0, 2), (-1, 2),  colors.HexColor("#dce8f0")),
                    ]))
                    story.append(t2)
                except ValueError:
                    pass

            # source line
            src_str  = ", ".join(sorted(sources))
            date_str = ", ".join(sorted(dates))
            if src_str:
                story.append(Spacer(1, 0.2*cm))
                story.append(Paragraph(f"Ціни: {src_str}{', ' + date_str if date_str else ''}.", note_s))

        story.append(Spacer(1, 0.4*cm))
        story.append(Paragraph(
            "Це середні ринкові ціни. Покажіть їх будівельникам при обговоренні ціни.",
            note_s
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
        self._knowledge_config = knowledge_config

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
            import traceback
            logger.error(f"[capability] '{name}' error: {e}\n{traceback.format_exc()}")
            return CapabilityResult(False, "Помилка виконання функції.", error=str(e))
