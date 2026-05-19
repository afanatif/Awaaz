from __future__ import annotations

from typing import Any

import requests
from bs4 import BeautifulSoup

from awaz_logger import awaz_log, LogTimer


BR_URLS = [
    "https://www.brecorder.com/",
    "https://www.brecorder.com/markets",
]


def fetch_business_recorder_news(limit: int = 8) -> dict[str, Any]:
    awaz_log(
        "ingestion", "source_fetch_started",
        input_summary="Business Recorder",
        output_summary=f"limit={limit}",
        endpoint=BR_URLS[0],
    )

    with LogTimer() as timer:
        for url in BR_URLS:
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

                parsed = _extract_headlines(resp.text, limit)
                if parsed:
                    result = {
                        "source": "Business Recorder",
                        "url": url,
                        "headlines": parsed,
                        "count": len(parsed),
                        "latency_ms": round(timer.elapsed_ms, 1),
                    }
                    awaz_log(
                        "ingestion", "source_fetch_completed",
                        input_summary="Business Recorder",
                        output_summary=f"{len(parsed)} headlines fetched",
                        duration_ms=timer.elapsed_ms,
                        result_count=len(parsed),
                    )
                    return result
            except Exception:
                continue

    awaz_log(
        "ingestion", "source_fetch_failed",
        input_summary="Business Recorder",
        error="Scrape failed — using fallback",
        duration_ms=timer.elapsed_ms,
    )
    return _fallback_business_recorder(limit)


def _extract_headlines(html: str, limit: int) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    results: list[dict[str, str]] = []
    seen: set[str] = set()

    for anchor in soup.select("a"):
        title = " ".join(anchor.get_text(" ", strip=True).split())
        href = (anchor.get("href") or "").strip()

        if len(title) < 25:
            continue
        if title.lower() in seen:
            continue
        if href and href.startswith("/"):
            href = f"https://www.brecorder.com{href}"
        if href and "brecorder.com" not in href:
            continue

        seen.add(title.lower())
        results.append({"title": title, "summary": title, "url": href})
        if len(results) >= limit:
            break

    return results


def _fallback_business_recorder(limit: int) -> dict[str, Any]:
    fallback = [
        {
            "title": "PSX investors remain cautious as inflation outlook stays mixed",
            "summary": "Local market sentiment is balanced between easing inflation hopes and policy uncertainty.",
            "url": "https://www.brecorder.com/",
        },
        {
            "title": "Rupee-dollar movement keeps import-heavy sectors under pressure",
            "summary": "Currency volatility is creating cost planning challenges for businesses relying on imports.",
            "url": "https://www.brecorder.com/",
        },
        {
            "title": "Energy and banking stocks lead recent volumes on Pakistan bourse",
            "summary": "Sector concentration in trading activity points to selective risk appetite.",
            "url": "https://www.brecorder.com/",
        },
    ]
    clipped = fallback[: max(1, min(limit, len(fallback)))]
    return {
        "source": "Business Recorder (simulated fallback)",
        "url": BR_URLS[0],
        "headlines": clipped,
        "count": len(clipped),
        "latency_ms": 0,
        "is_fallback": True,
    }
