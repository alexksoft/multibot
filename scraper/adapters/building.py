"""
Demo SourceAdapter for building materials reference prices.
Replace with real HTTP scraping of allowed sources in production.
Respects robots.txt and uses polite delays.
"""
from __future__ import annotations
import asyncio
import logging
from datetime import date

from ..base import ScrapedRow

logger = logging.getLogger(__name__)

CRAWL_DELAY = 2.0


class BuildingMaterialsAdapter:
    name = "demo_building_reference"
    base_url = "https://example-building-reference.ua"

    async def fetch(self, category: str) -> list[ScrapedRow]:
        today = date.today().strftime("%Y-%m")
        demo_data: dict[str, list[ScrapedRow]] = {
            "Фарба": [
                ScrapedRow(category="Фарба", item="Інтер'єрна біла 10л", price=450.0, unit="грн",
                           source_name="Довідник цін будматеріалів", source_url="https://example.ua/farba",
                           collected_at=today),
                ScrapedRow(category="Фарба", item="Фасадна 10л", price=680.0, unit="грн",
                           source_name="Довідник цін будматеріалів", source_url="https://example.ua/farba-fasad",
                           collected_at=today),
            ],
            "Штукатурка": [
                ScrapedRow(category="Штукатурка", item="Цементна 25кг", price=180.0, unit="грн",
                           source_name="Довідник цін будматеріалів", source_url="https://example.ua/shtuk",
                           collected_at=today),
            ],
            "Шпаклівка": [
                ScrapedRow(category="Шпаклівка", item="Фінішна 25кг", price=220.0, unit="грн",
                           source_name="Довідник цін будматеріалів", source_url="https://example.ua/shpakl",
                           collected_at=today),
            ],
            "Ґрунтовка": [
                ScrapedRow(category="Ґрунтовка", item="Глибокого проникнення 10л", price=160.0, unit="грн",
                           source_name="Довідник цін будматеріалів", source_url="https://example.ua/grunt",
                           collected_at=today),
            ],
        }
        await asyncio.sleep(CRAWL_DELAY)
        return demo_data.get(category, [])
