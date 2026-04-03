"""
Market news ticker endpoint — returns latest carbon market headlines.
Public endpoint, no auth required (same as price data).
"""
import logging

from fastapi import APIRouter

from ...services.news_scraper import news_scraper

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/market", tags=["market-news"])


@router.get("/news")
async def get_news_ticker():
    """
    Returns latest carbon market headlines for the news ticker.
    Served from Redis cache (refreshed every 20 min by background task).
    Falls back to live fetch if cache is empty.
    """
    headlines = await news_scraper.get_headlines()
    return {"headlines": headlines, "count": len(headlines)}
