# sources/news_fetcher.py
#
# Awaz — NewsAPI source fetcher.
# Fetches top headlines using keywords extracted from user claim.

from __future__ import annotations

import os
import time
from typing import Any

import requests

from awaz_logger import awaz_log, LogTimer


def fetch_news(keywords: list[str]) -> dict[str, Any]:
    """
    Query NewsAPI for articles matching the given keywords.

    Parameters
    ----------
    keywords : list of 3-5 search terms extracted from the user's claim

    Returns
    -------
    dict with keys: articles (list), total_results (int), keywords_used, latency_ms
    """
    api_key = os.environ.get("NEWSAPI_KEY", "")

    if not api_key:
        awaz_log(
            "ingestion", "source_fetch_failed",
            input_summary="NewsAPI",
            error="NEWSAPI_KEY not set — using fallback",
        )
        return _fallback_news(keywords)

    query = " OR ".join(keywords)
    endpoint = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "sortBy": "publishedAt",
        "pageSize": 20,
        "language": "en",
        "apiKey": api_key,
    }

    awaz_log(
        "ingestion", "source_fetch_started",
        input_summary="NewsAPI",
        output_summary=f"keywords={keywords}",
        endpoint=endpoint,
    )

    with LogTimer() as timer:
        try:
            resp = requests.get(endpoint, params=params, timeout=15)
            data = resp.json()
        except Exception as exc:
            awaz_log(
                "ingestion", "source_fetch_failed",
                input_summary="NewsAPI",
                error=str(exc),
                fallback="returning empty results",
            )
            return _fallback_news(keywords)

    if data.get("status") != "ok":
        awaz_log(
            "ingestion", "source_fetch_failed",
            input_summary="NewsAPI",
            error=data.get("message", "Unknown API error"),
            duration_ms=timer.elapsed_ms,
        )
        return _fallback_news(keywords)

    articles = data.get("articles", [])
    result = {
        "source": "NewsAPI",
        "articles": [
            {
                "title": a.get("title", ""),
                "description": a.get("description", ""),
                "source_name": a.get("source", {}).get("name", ""),
                "published_at": a.get("publishedAt", ""),
                "url": a.get("url", ""),
            }
            for a in articles[:20]
        ],
        "total_results": data.get("totalResults", 0),
        "keywords_used": keywords,
        "latency_ms": round(timer.elapsed_ms, 1),
    }

    awaz_log(
        "ingestion", "source_fetch_completed",
        input_summary="NewsAPI",
        output_summary=f"{len(result['articles'])} articles fetched",
        duration_ms=timer.elapsed_ms,
        result_count=len(result["articles"]),
    )

    return result


def _fallback_news(keywords: list[str]) -> dict[str, Any]:
    """Return simulated news data when API is unavailable."""
    simulated = [
        {
            "title": f"Market analysis: {keywords[0] if keywords else 'sector'} shows mixed signals amid global uncertainty",
            "description": "Analysts are divided on the short-term outlook as multiple factors influence the market direction.",
            "source_name": "Reuters (simulated)",
            "published_at": "2025-01-15T10:00:00Z",
            "url": "https://example.com/simulated",
        },
        {
            "title": f"OPEC+ discusses production targets as {keywords[0] if keywords else 'energy'} demand fluctuates",
            "description": "The organization is weighing supply adjustments in response to changing global demand patterns.",
            "source_name": "Bloomberg (simulated)",
            "published_at": "2025-01-14T08:30:00Z",
            "url": "https://example.com/simulated2",
        },
        {
            "title": f"Pakistan's economic indicators show cautious optimism for {keywords[0] if keywords else 'trade'} sector",
            "description": "Government reports suggest stabilization but challenges remain in the current fiscal environment.",
            "source_name": "Dawn (simulated)",
            "published_at": "2025-01-13T12:00:00Z",
            "url": "https://example.com/simulated3",
        },
    ]
    return {
        "source": "NewsAPI (simulated fallback)",
        "articles": simulated,
        "total_results": len(simulated),
        "keywords_used": keywords,
        "latency_ms": 0,
        "is_fallback": True,
    }
