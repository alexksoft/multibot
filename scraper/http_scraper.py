"""
Real HTTP scraper for building materials prices.
Respects robots.txt, uses polite delays, proper User-Agent.
"""
from __future__ import annotations
import asyncio
import logging
import re
from datetime import date
from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse

import httpx

from .base import ScrapedRow

logger = logging.getLogger(__name__)

USER_AGENT = "PracticalAIAssistantsBot/1.0 (educational demo scraper)"
CRAWL_DELAY = 2.0
TIMEOUT = 15.0


def check_robots(base_url: str, path: str) -> bool:
    """Return True if crawling is allowed by robots.txt."""
    try:
        rp = RobotFileParser()
        rp.set_url(f"{base_url}/robots.txt")
        rp.read()
        allowed = rp.can_fetch(USER_AGENT, f"{base_url}{path}")
        delay = rp.crawl_delay(USER_AGENT) or rp.crawl_delay("*")
        return allowed, float(delay) if delay else CRAWL_DELAY
    except Exception as e:
        logger.warning(f"[robots] Could not read {base_url}/robots.txt: {e}")
        return True, CRAWL_DELAY


async def check_robots_async(url: str) -> dict:
    """Check robots.txt for a URL. Returns dict with allowed, delay, details."""
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path or "/"
    try:
        async with httpx.AsyncClient(timeout=8, headers={"User-Agent": USER_AGENT}) as client:
            r = await client.get(f"{base}/robots.txt")
            robots_text = r.text if r.status_code == 200 else ""
    except Exception as e:
        return {"allowed": True, "delay": CRAWL_DELAY, "robots_url": f"{base}/robots.txt",
                "error": str(e), "content": ""}

    rp = RobotFileParser()
    rp.set_url(f"{base}/robots.txt")
    rp.parse(robots_text.splitlines())
    allowed = rp.can_fetch(USER_AGENT, url)
    delay = rp.crawl_delay(USER_AGENT) or rp.crawl_delay("*") or CRAWL_DELAY

    return {
        "allowed": allowed,
        "delay": float(delay),
        "robots_url": f"{base}/robots.txt",
        "error": None,
        "content": robots_text[:500],
    }


class GenericAIAdapter:
    """
    Universal adapter: fetches any category page and uses AI to extract
    product names and prices. Works for any site without site-specific code.
    """

    def __init__(self, source_name: str, base_url: str,
                 kiro_url: str = "", kiro_key: str = ""):
        self.name = source_name
        self.base_url = base_url
        self._kiro_url = kiro_url
        self._kiro_key = kiro_key

    async def fetch(self, category: str, url: str) -> list[ScrapedRow]:
        today = date.today().strftime("%Y-%m")
        rows = []

        # Fetch the page
        try:
            async with httpx.AsyncClient(
                timeout=TIMEOUT,
                headers={"User-Agent": USER_AGENT, "Accept-Language": "uk,en;q=0.9"},
                follow_redirects=True,
            ) as client:
                await asyncio.sleep(CRAWL_DELAY)
                resp = await client.get(url)
                if resp.status_code != 200:
                    logger.warning(f"[{self.name}] {url} returned {resp.status_code}")
                    return []
                html = resp.text
        except Exception as e:
            logger.error(f"[{self.name}] fetch failed {url}: {e}")
            return []

        # Try JSON-LD first (fast, no AI needed)
        import json
        jsonld_rows = self._parse_jsonld(html, category, url, today)
        if jsonld_rows:
            logger.info(f"[{self.name}] {category}: {len(jsonld_rows)} items via JSON-LD")
            return jsonld_rows

        # Fallback: AI extraction
        if self._kiro_url and self._kiro_key:
            ai_rows = await self._parse_with_ai(html, category, url, today)
            if ai_rows:
                logger.info(f"[{self.name}] {category}: {len(ai_rows)} items via AI")
                return ai_rows

        logger.warning(f"[{self.name}] {category}: no items extracted from {url}")
        return []

    def _parse_jsonld(self, html: str, category: str, url: str, today: str) -> list[ScrapedRow]:
        import json
        rows = []
        for match in re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html, re.DOTALL
        ):
            try:
                data = json.loads(match.strip())
                items = []
                if isinstance(data, dict) and data.get("@type") == "ItemList":
                    items = data.get("itemListElement", [])
                elif isinstance(data, list):
                    items = data
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    offer = item.get("offers") or item.get("offer") or {}
                    if isinstance(offer, list):
                        offer = offer[0] if offer else {}
                    price = offer.get("price") or item.get("price")
                    name = item.get("name", "")
                    item_url = item.get("url", url)
                    if price and name:
                        try:
                            rows.append(ScrapedRow(
                                category=category, item=name[:100],
                                price=float(str(price).replace(" ", "").replace(",", ".")),
                                unit="грн", source_name=self.name,
                                source_url=item_url, collected_at=today,
                            ))
                        except (ValueError, TypeError):
                            pass
            except Exception:
                pass
        return rows

    async def _parse_with_ai(self, html: str, category: str,
                              url: str, today: str) -> list[ScrapedRow]:
        import json
        # Trim HTML to fit in context — keep first 8000 chars (product listings are near top)
        html_snippet = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        html_snippet = re.sub(r'<style[^>]*>.*?</style>', '', html_snippet, flags=re.DOTALL)
        html_snippet = re.sub(r'<[^>]+>', ' ', html_snippet)
        html_snippet = re.sub(r'\s+', ' ', html_snippet).strip()[:6000]

        prompt = (
            f"Extract product listings from this Ukrainian shop page for category '{category}'.\n"
            f"Page URL: {url}\n"
            f"Return ONLY a JSON array, no markdown. Each item:\n"
            f'{{"name": "product name", "price": 123.0, "unit": "грн"}}\n'
            f"Extract up to 30 items. If no prices found, return [].\n\n"
            f"Page text:\n{html_snippet}"
        )
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self._kiro_url}/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self._kiro_key}",
                             "Content-Type": "application/json"},
                    json={"model": "claude-haiku-4.5", "max_tokens": 1500,
                          "messages": [{"role": "user", "content": prompt}]},
                )
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
                content = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                items = json.loads(content)
                rows = []
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    price = item.get("price")
                    name = item.get("name", "")
                    if price and name:
                        rows.append(ScrapedRow(
                            category=category, item=str(name)[:100],
                            price=float(price), unit=item.get("unit", "грн"),
                            source_name=self.name, source_url=url,
                            collected_at=date.today().strftime("%Y-%m"),
                        ))
                return rows
        except Exception as e:
            logger.warning(f"[{self.name}] AI parse failed: {e}")
            return []
    """Scrapes product listings from epicentrk.ua category pages."""
    name = "Епіцентр"
    base_url = "https://epicentrk.ua"

    async def fetch(self, category: str, url: str) -> list[ScrapedRow]:
        today = date.today().strftime("%Y-%m")
        rows = []

        try:
            async with httpx.AsyncClient(
                timeout=TIMEOUT,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept-Language": "uk,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml",
                },
                follow_redirects=True,
            ) as client:
                await asyncio.sleep(CRAWL_DELAY)
                resp = await client.get(url)
                if resp.status_code != 200:
                    logger.warning(f"[epicentr] {url} returned {resp.status_code}")
                    return []
                html = resp.text
        except Exception as e:
            logger.error(f"[epicentr] fetch failed {url}: {e}")
            return []

        # Parse product cards — Epicentr uses structured data in JSON-LD
        # Try JSON-LD first (most reliable)
        import json
        jsonld_matches = re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html, re.DOTALL
        )
        for match in jsonld_matches:
            try:
                data = json.loads(match.strip())
                items = []
                if isinstance(data, dict) and data.get("@type") == "ItemList":
                    items = data.get("itemListElement", [])
                elif isinstance(data, list):
                    items = data
                for item in items:
                    if isinstance(item, dict):
                        offer = item.get("offers", item.get("offer", {}))
                        if isinstance(offer, list):
                            offer = offer[0] if offer else {}
                        price = offer.get("price") or item.get("price")
                        name = item.get("name", "")
                        item_url = item.get("url", url)
                        if price and name:
                            try:
                                rows.append(ScrapedRow(
                                    category=category,
                                    item=name[:100],
                                    price=float(str(price).replace(" ", "").replace(",", ".")),
                                    unit="грн",
                                    source_name=self.name,
                                    source_url=item_url,
                                    collected_at=today,
                                ))
                            except (ValueError, TypeError):
                                pass
            except (json.JSONDecodeError, Exception):
                pass

        # Fallback: parse HTML price patterns
        if not rows:
            rows = self._parse_html(html, category, url, today)

        logger.info(f"[epicentr] {category}: {len(rows)} items from {url}")
        return rows  # no artificial limit

    def _parse_html(self, html: str, category: str, url: str, today: str) -> list[ScrapedRow]:
        """Fallback HTML parser for product names and prices."""
        rows = []
        # Match price patterns like: 1 234 грн, 450грн
        price_pattern = re.compile(r'(\d[\d\s]{1,8})\s*грн', re.IGNORECASE)
        # Match product title patterns
        title_pattern = re.compile(
            r'(?:class="[^"]*(?:title|name|product)[^"]*"[^>]*>|<h[23][^>]*>)\s*([^<]{5,100})',
            re.IGNORECASE
        )
        titles = [m.group(1).strip() for m in title_pattern.finditer(html)][:20]
        prices = [float(m.group(1).replace(" ", "")) for m in price_pattern.finditer(html)][:20]

        for i, (title, price) in enumerate(zip(titles, prices)):
            if price > 0:
                rows.append(ScrapedRow(
                    category=category,
                    item=title[:100],
                    price=price,
                    unit="грн",
                    source_name=self.name,
                    source_url=url,
                    collected_at=today,
                ))
        return rows


async def run_scraper(bot_name: str, config: dict, creds_path: str, sheet_id: str,
                      worksheet: str, kiro_url: str = "", kiro_key: str = "") -> dict:
    """
    Run scraper for a bot. Returns result summary.
    config = list of {name, base_url, categories: [{name, url}]}
    """
    from .base import SheetsWriter, ScrapedRow, _SHEET_HEADER

    all_rows: list[ScrapedRow] = []
    errors = []
    skipped = []

    for source in config:
        source_name = source.get("name", "")
        base_url = source.get("base_url", "")

        for cat in source.get("categories", []):
            cat_name = cat["name"]
            cat_url = cat["url"]

            # Check robots.txt
            result = await check_robots_async(cat_url)
            if not result["allowed"]:
                msg = f"{source_name}/{cat_name}: заборонено robots.txt"
                logger.warning(f"[scraper] {msg}")
                skipped.append(msg)
                continue

            # Scrape using universal AI adapter
            try:
                adapter = GenericAIAdapter(
                    source_name=source_name,
                    base_url=base_url,
                    kiro_url=kiro_url or "",
                    kiro_key=kiro_key or "",
                )
                rows = await adapter.fetch(cat_name, cat_url)
                all_rows.extend(rows)
                await asyncio.sleep(result["delay"])
            except Exception as e:
                msg = f"{source_name}/{cat_name}: {e}"
                logger.error(f"[scraper] {msg}")
                errors.append(msg)

    # Write to Sheets
    written = 0
    if all_rows and sheet_id and creds_path:
        try:
            writer = SheetsWriter(creds_path, sheet_id)
            writer.recreate(worksheet, all_rows)
            written = len(all_rows)
        except Exception as e:
            errors.append(f"Sheets write: {e}")

    return {
        "bot": bot_name,
        "rows_collected": len(all_rows),
        "rows_written": written,
        "skipped": skipped,
        "errors": errors,
    }
