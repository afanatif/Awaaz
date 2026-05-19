from __future__ import annotations

from typing import Any

import requests
from bs4 import BeautifulSoup

from awaz_logger import awaz_log, LogTimer


PROFIT_URLS = [
    "https://profit.pakistantoday.com.pk/",
    "https://profit.pakistantoday.com.pk/category/news/",
]


def fetch_profit_pakistan_news(limit: int = 8) -> dict[str, Any]:
    awaz_log(
        "ingestion", "source_fetch_started",
        input_summary="Profit Pakistan",
        output_summary=f"limit={limit}",
        endpoint=PROFIT_URLS[0],
    )

    with LogTimer() as timer:
        for url in PROFIT_URLS:
            try:
                resp = requests.get(
                    url,
                    timeout=12,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/124.0.0.0 Safari/537.36"
                        )
                    },
                )
                if resp.status_code >= 400 or not resp.text.strip():
                    continue

                headlines = _extract_headlines(resp.text, limit)
                if headlines:
                    result = {
                        "source": "Profit Pakistan",
                        "url": url,
                        "headlines": headlines,
                        "count": len(headlines),
                        "latency_ms": round(timer.elapsed_ms, 1),
                    }
                    awaz_log(
                        "ingestion", "source_fetch_completed",
                        input_summary="Profit Pakistan",
                        output_summary=f"{len(headlines)} headlines fetched",
                        duration_ms=timer.elapsed_ms,
                        result_count=len(headlines),
                    )
                    return result
            except Exception:
                continue

    awaz_log(
        "ingestion", "source_fetch_failed",
        input_summary="Profit Pakistan",
        error="Scrape failed — using fallback",
        duration_ms=timer.elapsed_ms,
    )
    return _fallback_profit(limit)


def _extract_headlines(html: str, limit: int) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    results: list[dict[str, str]] = []
    seen: set[str] = set()

    selectors = [
        "h2.entry-title a",
        "h3.entry-title a",
        "article h2 a",
        "article h3 a",
        "a",
    ]

    for selector in selectors:
        for anchor in soup.select(selector):
            title = " ".join(anchor.get_text(" ", strip=True).split())
            href = (anchor.get("href") or "").strip()

            if len(title) < 24:
                continue
            if title.lower() in seen:
                continue
            if href and href.startswith("/"):
                href = f"https://profit.pakistantoday.com.pk{href}"
            if href and "profit.pakistantoday.com.pk" not in href:
                continue

            seen.add(title.lower())
            results.append({"title": title, "summary": title, "url": href or PROFIT_URLS[0]})
            if len(results) >= limit:
                return results

    return results


def _fallback_profit(limit: int) -> dict[str, Any]:
    fallback = [
        {
            "title": "Policy and power-tariff expectations shape short-term industrial outlook",
            "summary": "Business coverage indicates cost-side uncertainty still dominates planning decisions.",
            "url": "https://profit.pakistantoday.com.pk/",
        },
        {
            "title": "Listed firms focus on cash preservation as financing remains expensive",
            "summary": "Corporate commentary reflects cautious capex strategy under tight credit conditions.",
            "url": "https://profit.pakistantoday.com.pk/",
        },
        {
            "title": "Analysts flag valuation gaps between cyclical and defensive sectors",
            "summary": "Recent market commentary highlights divergence in risk appetite across sectors.",
            "url": "https://profit.pakistantoday.com.pk/",
        },
    ]
    clipped = fallback[: max(1, min(limit, len(fallback)))]
    return {
        "source": "Profit Pakistan (simulated fallback)",
        "url": PROFIT_URLS[0],
        "headlines": clipped,
        "count": len(clipped),
        "latency_ms": 0,
        "is_fallback": True,
    }
