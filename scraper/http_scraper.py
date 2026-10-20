"""
Real HTTP scraper for building materials prices.
Respects robots.txt, uses polite delays, proper User-Agent.
"""
from __future__ import annotations
import asyncio
import json
import logging
import re
from datetime import date
from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse, urlunparse, parse_qs

import httpx

from .base import ScrapedRow

logger = logging.getLogger(__name__)

USER_AGENT = "PracticalAIAssistantsBot/1.0 (educational demo scraper)"
CRAWL_DELAY = 2.0
TIMEOUT = 15.0
MAX_PAGES = 5

# Price patterns on product pages
_PRICE_PAIR_RE = re.compile(
    r'([\d]+(?:[.,]\d+)?)\s*[₴грн]+\s*за\s*1\s*уп\.?\s*/\s*([\d]+(?:[.,]\d+)?)\s*[₴грн]+\s*за\s*1\s*кв\.?\s*м',
    re.IGNORECASE
)
_PRICE_PER_M2_RE = re.compile(
    r'([\d]+(?:[.,]\d+)?)\s*(?:₴|грн)\s*/\s*кв\.?\s*м',
    re.IGNORECASE
)
_NUM_RE = re.compile(r'([\d]+(?:[.,]\d+)?)')
_VALUE_NUM_UNIT_RE = re.compile(
    r'([\d]+(?:[.,]\d+)?)\s*(кг|г|л|мл|м²|м2|шт|рул|пач)\b',
    re.IGNORECASE
)


def _normalize_weight(value: float, unit: str) -> tuple:
    if unit.lower() == "г":
        return value / 1000, "кг"
    return value, unit


def _extract_pkg_from_chars(chars: dict) -> tuple:
    # Priority 1: tile — area per package
    for key, val in chars.items():
        kl = key.lower()
        if "кількість" in kl and "упак" in kl and "кв.м" in kl:
            m = _NUM_RE.search(val)
            if m:
                return _n(m.group(1)), "м²"

    # Priority 2: фасування — actual packaging size
    for key, val in chars.items():
        if key.lower().startswith("фасування"):
            m = _VALUE_NUM_UNIT_RE.search(val)
            if m:
                return _normalize_weight(_n(m.group(1)), m.group(2))

    # Priority 3: об'єм — volume in litres (paint, primer) — before weight
    for key, val in chars.items():
        kl = key.lower()
        if kl.startswith("об'єм") or kl.startswith("обєм") or kl.startswith("об\u2019єм") or kl.startswith("об`єм"):
            m = _VALUE_NUM_UNIT_RE.search(val)
            if m:
                return _n(m.group(1)), m.group(2)

    # Priority 4: вага упаковки — fallback with gram→kg conversion
    for key, val in chars.items():
        if key.lower().startswith("вага"):
            m = _VALUE_NUM_UNIT_RE.search(val)
            if m:
                return _normalize_weight(_n(m.group(1)), m.group(2))
            m = _NUM_RE.search(val)
            if m:
                return _normalize_weight(_n(m.group(1)), "кг")

    return None, None


def _n(s: str) -> float:
    return float(s.replace(',', '.'))


def check_robots(base_url: str, path: str):
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
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
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
    return {"allowed": allowed, "delay": float(delay),
            "robots_url": f"{base}/robots.txt", "error": None, "content": robots_text[:500]}


def _page_url(url: str, page: int) -> str:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    qs["page"] = [str(page)]
    new_query = "&".join(f"{k}={v[0]}" for k, v in qs.items())
    return urlunparse(parsed._replace(query=new_query))


async def _fetch_product_chars(url: str, client: httpx.AsyncClient) -> dict:
    """
    Fetch product page, extract package_size, package_unit, and price_per_m2
    using BeautifulSoup for robust dt/dd parsing.

    Returns dict with keys: package_size, package_unit, price_per_m2
    """
    result = {"package_size": None, "package_unit": None, "price_per_m2": None}
    try:
        await asyncio.sleep(0.3)
        r = await client.get(url)
        if r.status_code != 200:
            return result
        html = r.text

        # --- Extract price per m² ---
        # Priority 1: explicit pair "X грн за 1 уп. / Y грн за 1 кв. м"
        m = _PRICE_PAIR_RE.search(html)
        if m:
            result["price_per_m2"] = _n(m.group(2))
        else:
            # Priority 2: standalone "N ₴/кв. м"
            m = _PRICE_PER_M2_RE.search(html)
            if m:
                result["price_per_m2"] = _n(m.group(1))

        # --- Extract package size using BeautifulSoup ---
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "lxml")
        except ImportError:
            soup = None

        if soup:
            chars = {}
            for dt in soup.find_all("dt"):
                dd = dt.find_next_sibling("dd")
                if dd:
                    key = dt.get_text(strip=True).rstrip(":")
                    val = dd.get_text(strip=True)
                    chars[key] = val
        else:
            # Fallback regex if BS4 not available
            pairs = re.findall(
                r'<dt[^>]*>\s*(?:<[^>]+>)*([^<]+)(?:<[^>]+>)*\s*</dt>\s*<dd[^>]*>\s*(?:<[^>]+>)*([^<]+)',
                html
            )
            chars = {k.strip().rstrip(":"): v.strip() for k, v in pairs}

        if not chars:
            logger.warning(f"[chars] Empty characteristics from {url}")

        result["package_size"], result["package_unit"] = _extract_pkg_from_chars(chars)

    except Exception as e:
        logger.warning(f"[chars] Failed for {url}: {e}")

    return result


async def _enrich_rows(rows: list[ScrapedRow], client: httpx.AsyncClient,
                       semaphore: asyncio.Semaphore) -> None:
    """
    Fetch product pages in parallel to get accurate package_size and price_per_m².
    Fix #1: always overwrite — never skip because name-regex already wrote a value.
    Fix #2: runs for ALL sources, not just epicentrk.ua.
    Fix #5: overwrite row.price with page-confirmed price_per_m² when available.
    """
    async def enrich_one(row: ScrapedRow):
        if not row.source_url:
            return
        async with semaphore:
            data = await _fetch_product_chars(row.source_url, client)

        # Always overwrite package_size from page (fix #1)
        if data["package_size"] is not None:
            row.package_size = data["package_size"]
            row.package_unit = data["package_unit"]

        # Overwrite price with page-confirmed price_per_m² (fix #5)
        if data["price_per_m2"] is not None:
            row.price = data["price_per_m2"]
            row.price_unit = "грн/м²"
        elif data["package_size"] and data["package_unit"] == "м²" and data["package_size"] > 0:
            # Normalize: per-package price → per-m² (Option A)
            row.price = round(row.price / data["package_size"], 2)
            row.price_unit = "грн/м²"

    await asyncio.gather(*[enrich_one(r) for r in rows])


class GenericAIAdapter:
    def __init__(self, source_name: str, base_url: str,
                 kiro_url: str = "", kiro_key: str = ""):
        self.name = source_name
        self.base_url = base_url.rstrip("/")
        self._kiro_url = kiro_url
        self._kiro_key = kiro_key

    async def fetch(self, category: str, url: str) -> list[ScrapedRow]:
        today = date.today().strftime("%Y-%m")
        all_rows: list[ScrapedRow] = []

        async with httpx.AsyncClient(
            timeout=TIMEOUT,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "uk,en;q=0.9"},
            follow_redirects=True,
        ) as client:
            for page in range(1, MAX_PAGES + 1):
                page_url = url if page == 1 else _page_url(url, page)
                await asyncio.sleep(CRAWL_DELAY)
                try:
                    resp = await client.get(page_url)
                    if resp.status_code != 200:
                        if page == 1:
                            logger.warning(f"[{self.name}] {page_url} returned {resp.status_code}")
                        break
                    html = resp.text
                except Exception as e:
                    logger.error(f"[{self.name}] fetch failed {page_url}: {e}")
                    break

                rows = self._parse_jsonld(html, category, page_url, today)
                if rows:
                    logger.info(f"[{self.name}] {category} p{page}: {len(rows)} items via JSON-LD")
                    all_rows.extend(rows)
                    if len(rows) < 10:
                        break
                    continue

                rows = self._parse_html(html, category, page_url, today)
                if rows:
                    logger.info(f"[{self.name}] {category} p{page}: {len(rows)} items via HTML")
                    all_rows.extend(rows)
                    if len(rows) < 10:
                        break
                    continue

                if page == 1 and self._kiro_url and self._kiro_key:
                    rows = await self._parse_with_ai(html, category, page_url, today)
                    if rows:
                        logger.info(f"[{self.name}] {category}: {len(rows)} items via AI")
                        all_rows.extend(rows)
                    else:
                        logger.warning(f"[{self.name}] {category}: no items extracted from {page_url}")
                else:
                    if page == 1:
                        logger.warning(f"[{self.name}] {category}: no items extracted from {page_url}")
                break

        # Fix #2: enrich ALL sources (removed epicentrk.ua domain gate)
        if all_rows:
            sem = asyncio.Semaphore(5)
            async with httpx.AsyncClient(
                timeout=TIMEOUT,
                headers={"User-Agent": USER_AGENT, "Accept-Language": "uk,en;q=0.9"},
                follow_redirects=True,
            ) as enrich_client:
                await _enrich_rows(all_rows, enrich_client, sem)
            logger.info(f"[{self.name}] {category}: enriched {len(all_rows)} rows")

        return all_rows

    def _parse_jsonld(self, html: str, category: str, url: str, today: str) -> list[ScrapedRow]:
        rows = []
        for match in re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html, re.DOTALL
        ):
            try:
                data = json.loads(match.strip())
            except Exception:
                continue

            candidates = []
            if isinstance(data, list):
                candidates = data
            elif isinstance(data, dict):
                t = data.get("@type", "")
                if t == "ItemList":
                    candidates = data.get("itemListElement", [])
                elif t in ("Product", "Offer"):
                    candidates = [data]
                elif "@graph" in data:
                    candidates = data["@graph"]

            for item in candidates:
                if not isinstance(item, dict):
                    continue
                if item.get("@type") == "ListItem" and "item" in item:
                    item = item["item"]
                if not isinstance(item, dict):
                    continue

                name = item.get("name", "")
                item_url = item.get("url", url)
                offer = item.get("offers") or item.get("offer") or item
                if isinstance(offer, list):
                    offer = offer[0] if offer else {}
                price_raw = offer.get("price") if isinstance(offer, dict) else None
                if price_raw is None:
                    price_raw = item.get("price")

                if not name or price_raw is None:
                    continue
                try:
                    price = float(str(price_raw).replace(" ", "").replace(",", "."))
                    if price <= 0:
                        continue
                    rows.append(ScrapedRow(
                        category=category, item=name[:100],
                        price=price, price_unit="грн",
                        source_name=self.name, source_url=item_url,
                        collected_at=today,
                    ))
                except (ValueError, TypeError):
                    pass
        return rows

    def _parse_html(self, html: str, category: str, url: str, today: str) -> list[ScrapedRow]:
        if "budpostach.ua" in self.base_url:
            return self._parse_budpostach(html, category, url, today)
        return []

    def _parse_budpostach(self, html: str, category: str, url: str, today: str) -> list[ScrapedRow]:
        names = re.findall(r'class="product-thumb__name[^"]*"[^>]*>([^<]{5,120})', html)
        prices_raw = re.findall(r'data-special="(\d+)"', html)
        if not prices_raw:
            prices_raw = re.findall(r'data-price="(\d+)"', html)

        rows = []
        for name, price_str in zip(names, prices_raw):
            name = name.strip()
            try:
                price = float(price_str)
                if price <= 0 or not name:
                    continue
                rows.append(ScrapedRow(
                    category=category, item=name[:100],
                    price=price, price_unit="грн",
                    source_name=self.name, source_url=url,
                    collected_at=date.today().strftime("%Y-%m"),
                ))
            except (ValueError, TypeError):
                pass
        return rows

    async def _parse_with_ai(self, html: str, category: str,
                              url: str, today: str) -> list[ScrapedRow]:
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()[:6000]

        prompt = (
            f"You are a price extraction bot. Extract ALL product listings from this Ukrainian shop page.\n"
            f"Category: '{category}'. Page: {url}\n"
            f"Rules:\n"
            f"- Return ONLY a JSON array, no markdown, no explanation\n"
            f'- Each element: {{"name": "full product name", "price": 123.0}}\n'
            f"- price must be a number (UAH), not a string\n"
            f"- Skip items without a clear price\n"
            f"- Extract up to 30 items\n"
            f"- If no products found, return []\n\n"
            f"Page text:\n{text}"
        )
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                resp = await client.post(
                    f"{self._kiro_url}/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self._kiro_key}",
                             "Content-Type": "application/json"},
                    json={"model": "claude-haiku-4.5", "max_tokens": 2000,
                          "messages": [{"role": "user", "content": prompt}]},
                )
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"].strip()
                content = re.sub(r'^```[a-z]*\n?', '', content)
                content = re.sub(r'\n?```$', '', content).strip()
                items = json.loads(content)
                rows = []
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    name = str(item.get("name", "")).strip()
                    price_raw = item.get("price")
                    if not name or price_raw is None:
                        continue
                    try:
                        price = float(str(price_raw).replace(" ", "").replace(",", "."))
                        if price <= 0:
                            continue
                        rows.append(ScrapedRow(
                            category=category, item=name[:100],
                            price=price, price_unit="грн",
                            source_name=self.name, source_url=url,
                            collected_at=today,
                        ))
                    except (ValueError, TypeError):
                        pass
                return rows
        except Exception as e:
            logger.warning(f"[{self.name}] AI parse failed for {url}: {e}")
            return []


async def run_scraper(bot_name: str, config: dict, creds_path: str, sheet_id: str,
                      worksheet: str, kiro_url: str = "", kiro_key: str = "") -> dict:
    from .base import SheetsWriter

    all_rows: list[ScrapedRow] = []
    errors = []
    skipped = []

    for source in config:
        source_name = source.get("name", "")
        base_url = source.get("base_url", "")

        for cat in source.get("categories", []):
            cat_name = cat["name"]
            cat_url = cat["url"]

            result = await check_robots_async(cat_url)
            if not result["allowed"]:
                msg = f"{source_name}/{cat_name}: заборонено robots.txt"
                logger.warning(f"[scraper] {msg}")
                skipped.append(msg)
                continue

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
