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

    async def cheapest_item(self, category: str) -> CatalogItem | None:
        """Return the cheapest item in a category (lowest price per unit)."""
        items = await self.list_items(category)
        with_price = [i for i in items if i.price is not None and i.price > 0]
        if not with_price:
            return items[0] if items else None
        return min(with_price, key=lambda i: i.price)

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
        price_str = ""
        if item.price is not None:
            price_int = int(item.price)
            if item.price == price_int:
                price_str = f"{price_int:,}".replace(",", " ")
            else:
                price_str = f"{item.price:,.2f}".replace(",", " ")
            price_str += f" {item.unit or 'грн'}"
        source = f" ({item.source_name})" if item.source_name else ""
        return price_str + source if price_str else "ціна невідома"

    def _fmt_num(self, price: float) -> str:
        price_int = int(price)
        if price == price_int:
            return f"{price_int:,}".replace(",", " ")
        return f"{price:,.2f}".replace(",", " ")
