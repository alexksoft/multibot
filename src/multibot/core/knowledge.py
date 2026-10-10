from __future__ import annotations
import logging
import re

from ..config.sections import CatalogItem, FAQItem, KnowledgeData
from .catalog import CatalogProvider

logger = logging.getLogger(__name__)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


class KnowledgeBase:
    def __init__(self, knowledge: KnowledgeData, catalog_provider: CatalogProvider):
        self._faq = knowledge.faq
        self._norms = knowledge.norms
        self._catalog = catalog_provider

    def match_faq(self, text: str) -> FAQItem | None:
        """Return best FAQ match by keyword overlap."""
        normalized = _normalize(text)
        best: FAQItem | None = None
        best_score = 0
        for item in self._faq:
            score = sum(1 for kw in item.keywords if kw.lower() in normalized)
            if score > best_score:
                best_score = score
                best = item
        return best if best_score > 0 else None

    async def list_items(self, category: str) -> list[CatalogItem]:
        all_items = await self._catalog.items()
        cat_lower = category.lower()
        return [i for i in all_items if i.category.lower() == cat_lower]

    async def find_item(self, category: str, item_name: str) -> CatalogItem | None:
        items = await self.list_items(category)
        name_lower = item_name.lower()
        for i in items:
            if name_lower in i.item.lower():
                return i
        return None

    async def list_categories(self) -> list[str]:
        all_items = await self._catalog.items()
        seen: list[str] = []
        for i in all_items:
            if i.category not in seen:
                seen.append(i.category)
        return seen

    def get_norms(self) -> dict[str, float]:
        return self._norms

    def format_price(self, item: CatalogItem) -> str:
        parts = []
        if item.price is not None:
            parts.append(f"{item.price} {item.unit or 'грн'}")
        if item.source_name:
            parts.append(item.source_name)
        if item.collected_at:
            parts.append(f"станом на {item.collected_at}")
        return ", ".join(parts) if parts else "ціна невідома"
