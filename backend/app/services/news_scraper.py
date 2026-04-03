"""
News scraper service — fetches RSS headlines from carbon/emissions market sources.
Uses built-in xml.etree + httpx (no extra deps). Caches in Redis.
"""
import asyncio
import json
import logging
import xml.etree.ElementTree as ET
from typing import Any

import httpx

logger = logging.getLogger(__name__)

NEWS_CACHE_KEY = "news_ticker_headlines"
NEWS_CACHE_TTL = 1500  # 25 minutes

# Carbon/emissions market RSS sources (public, no paywall)
NEWS_SOURCES = [
    {
        "name": "Carbon Pulse",
        "url": "https://carbon-pulse.com/feed/",
        "max_items": 6,
        "filter_keywords": [],  # already domain-specific, no filtering needed
    },
    {
        "name": "Carbon Brief",
        "url": "https://www.carbonbrief.org/feed",
        "max_items": 4,
        "filter_keywords": ["carbon", "emissions", "ETS", "EUA", "allowance", "climate", "CO2", "net zero"],
    },
    {
        "name": "Env. Finance",
        "url": "https://www.environmentalfinance.com/content/news/rss.xml",
        "max_items": 3,
        "filter_keywords": ["carbon", "emissions", "ETS", "allowance", "offset", "green"],
    },
]

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; NihaNewsBot/1.0; +https://niha.group)",
    "Accept": "application/rss+xml, application/xml, text/xml",
}


def _parse_rss(xml_text: str, source_name: str, max_items: int, keywords: list[str]) -> list[dict[str, Any]]:
    """Parse RSS/Atom XML and return filtered headlines."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.warning(f"[news] XML parse error for {source_name}: {e}")
        return []

    # Support both RSS 2.0 (<item>) and Atom (<entry>)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items = root.findall(".//item")
    if not items:
        items = root.findall(".//atom:entry", ns)

    headlines: list[dict[str, Any]] = []
    for item in items:
        # NOTE: must use `is None` check — bool(element) is False for leaf elements
        title_el = item.find("title")
        if title_el is None:
            title_el = item.find("atom:title", ns)
        if title_el is None:
            continue
        title = (title_el.text or "").strip()
        if not title:
            continue

        # Keyword filter (empty list = accept all)
        if keywords and not any(kw.lower() in title.lower() for kw in keywords):
            continue

        headlines.append({"title": title, "source": source_name})
        if len(headlines) >= max_items:
            break

    return headlines


async def _fetch_source(src: dict[str, Any]) -> list[dict[str, Any]]:
    """Fetch and parse one RSS source, returning [] on any error."""
    try:
        async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
            resp = await client.get(src["url"], headers=_HEADERS)
            resp.raise_for_status()
        return _parse_rss(resp.text, src["name"], src["max_items"], src["filter_keywords"])
    except Exception as exc:
        logger.warning(f"[news] Failed to fetch {src['name']}: {exc}")
        return []


class NewsScraper:
    async def refresh(self) -> list[dict[str, Any]]:
        """Fetch all sources concurrently, merge, cache in Redis."""
        results = await asyncio.gather(*[_fetch_source(s) for s in NEWS_SOURCES], return_exceptions=True)
        headlines: list[dict[str, Any]] = []
        for r in results:
            if isinstance(r, list):
                headlines.extend(r)

        if headlines:
            try:
                from ..core.security import RedisManager
                redis = await RedisManager.get_redis()
                await redis.setex(NEWS_CACHE_KEY, NEWS_CACHE_TTL, json.dumps(headlines))
                logger.info(f"[news] Cached {len(headlines)} headlines")
            except Exception as e:
                logger.warning(f"[news] Redis cache write failed: {e}")

        return headlines

    async def get_headlines(self) -> list[dict[str, Any]]:
        """Return cached headlines, refreshing if cache is empty."""
        try:
            from ..core.security import RedisManager
            redis = await RedisManager.get_redis()
            cached = await redis.get(NEWS_CACHE_KEY)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"[news] Redis cache read failed: {e}")

        return await self.refresh()


news_scraper = NewsScraper()
