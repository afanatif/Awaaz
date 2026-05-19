from __future__ import annotations

from typing import Any

import requests
from bs4 import BeautifulSoup

from awaz_logger import awaz_log, LogTimer


DAWN_URLS = [
    "https://www.dawn.com/business",
    "https://www.dawn.com/latest-news",
]


def fetch_dawn_business_news(limit: int = 8) -> dict[str, Any]:
    awaz_log(
        "ingestion", "source_fetch_started",
        input_summary="Dawn Business",
        output_summary=f"limit={limit}",
        endpoint=DAWN_URLS[0],
    )

    with LogTimer() as timer:
        for url in DAWN_URLS:
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
                        "source": "Dawn Business",
                        "url": url,
                        "headlines": headlines,
                        "count": len(headlines),
                        "latency_ms": round(timer.elapsed_ms, 1),
                    }
                    awaz_log(
                        "ingestion", "source_fetch_completed",
                        input_summary="Dawn Business",
                        output_summary=f"{len(headlines)} headlines fetched",
                        duration_ms=timer.elapsed_ms,
                        result_count=len(headlines),
                    )
                    return result
            except Exception:
                continue

    awaz_log(
        "ingestion", "source_fetch_failed",
        input_summary="Dawn Business",
        error="Scrape failed — using fallback",
        duration_ms=timer.elapsed_ms,
    )
    return _fallback_dawn(limit)


def _extract_headlines(html: str, limit: int) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    results: list[dict[str, str]] = []
    seen: set[str] = set()

    selectors = [
        "article h2 a",
        "article h3 a",
        ".story__content h2 a",
        ".story__content h3 a",
        "a.story__link",
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
                href = f"https://www.dawn.com{href}"
            if href and "dawn.com" not in href:
                continue

            seen.add(title.lower())
            results.append({"title": title, "summary": title, "url": href or DAWN_URLS[0]})
            if len(results) >= limit:
                return results

    return results


def _fallback_dawn(limit: int) -> dict[str, Any]:
    fallback = [
        {
            "title": "Pakistan exporters seek policy continuity amid shifting regional demand",
            "summary": "Business stakeholders stress predictable regulation as external demand cycles fluctuate.",
            "url": "https://www.dawn.com/business",
        },
        {
            "title": "Manufacturing activity shows selective recovery in large-scale segments",
            "summary": "Industrial output signals remain mixed as input costs and financing conditions vary by sector.",
            "url": "https://www.dawn.com/business",
        },
        {
            "title": "Banks and energy firms continue to drive index-heavy trading sessions",
            "summary": "Market breadth remains uneven despite stronger turnover in heavyweight sectors.",
            "url": "https://www.dawn.com/business",
        },
    ]
    clipped = fallback[: max(1, min(limit, len(fallback)))]
    return {
        "source": "Dawn Business (simulated fallback)",
        "url": DAWN_URLS[0],
        "headlines": clipped,
        "count": len(clipped),
        "latency_ms": 0,
        "is_fallback": True,
    }
