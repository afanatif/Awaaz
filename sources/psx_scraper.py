from __future__ import annotations

import re
from typing import Any

import requests
from bs4 import BeautifulSoup

from awaz_logger import awaz_log, LogTimer


PSX_URLS = [
    "https://dps.psx.com.pk/",
    "https://dps.psx.com.pk/indices/KSE100",
]


def fetch_psx_snapshot() -> dict[str, Any]:
    awaz_log(
        "ingestion", "source_fetch_started",
        input_summary="PSX Data Portal",
        endpoint=PSX_URLS[0],
    )

    with LogTimer() as timer:
        for url in PSX_URLS:
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

                parsed = _extract_kse100(resp.text)
                if parsed:
                    result = {
                        "source": "PSX",
                        "url": url,
                        "index": "KSE-100",
                        "index_value": parsed["index_value"],
                        "net_change": parsed["net_change"],
                        "pct_change": parsed["pct_change"],
                        "summary": (
                            f"KSE-100 at {parsed['index_value']:.2f}, "
                            f"change {parsed['net_change']:+.2f} "
                            f"({parsed['pct_change']:+.2f}%)"
                        ),
                        "latency_ms": round(timer.elapsed_ms, 1),
                    }
                    awaz_log(
                        "ingestion", "source_fetch_completed",
                        input_summary="PSX Data Portal",
                        output_summary=result["summary"],
                        duration_ms=timer.elapsed_ms,
                    )
                    return result
            except Exception:
                continue

    awaz_log(
        "ingestion", "source_fetch_failed",
        input_summary="PSX Data Portal",
        error="Scrape failed — using fallback",
        duration_ms=timer.elapsed_ms,
    )
    return _fallback_psx()


def _extract_kse100(html: str) -> dict[str, float] | None:
    soup = BeautifulSoup(html, "lxml")
    text = " ".join(soup.get_text(" ", strip=True).split())

    match = re.search(
        r"KSE\s*-?\s*100[^\d]*(\d{2,}(?:,\d{3})*(?:\.\d+)?)"
        r"[^\d+-]*([+-]?\d+(?:\.\d+)?)"
        r"[^\d+-]*([+-]?\d+(?:\.\d+)?)%",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None

    index_value = float(match.group(1).replace(",", ""))
    net_change = float(match.group(2))
    pct_change = float(match.group(3))
    return {
        "index_value": index_value,
        "net_change": net_change,
        "pct_change": pct_change,
    }


def _fallback_psx() -> dict[str, Any]:
    return {
        "source": "PSX (simulated fallback)",
        "url": PSX_URLS[0],
        "index": "KSE-100",
        "index_value": 73540.25,
        "net_change": -182.40,
        "pct_change": -0.25,
        "summary": "KSE-100 at 73540.25, change -182.40 (-0.25%)",
        "latency_ms": 0,
        "is_fallback": True,
    }
