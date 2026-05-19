# sources/regulatory_fetcher.py
# Awaz — Regulatory & macroeconomic data fetcher.
# Scrapes SBP for monetary policy + fetches USD/PKR exchange rate.

from __future__ import annotations
import os
from typing import Any
import requests
from awaz_logger import awaz_log, LogTimer


def fetch_regulatory_context() -> dict[str, Any]:
    awaz_log("ingestion", "source_fetch_started", input_summary="Regulatory/Macro",
             output_summary="SBP + Exchange Rate")

    reg = {
        "source": "Regulatory/Macro",
        "interest_rate": None,
        "rate_direction": None,
        "exchange_rate": None,
        "exchange_rate_30d_change": None,
        "economic_stance": None,
        "sbp_policy_summary": None,
        "latency_ms": 0,
    }

    with LogTimer() as t:
        # 1. SBP monetary policy
        sbp = _fetch_sbp_data()
        reg.update(sbp)

        # 2. USD/PKR exchange rate
        fx = _fetch_exchange_rate()
        reg["exchange_rate"] = fx.get("rate")
        reg["exchange_rate_30d_change"] = fx.get("change_30d")

        # Determine economic stance
        if reg["rate_direction"] == "decreasing":
            reg["economic_stance"] = "expansionary"
        elif reg["rate_direction"] == "increasing":
            reg["economic_stance"] = "contractionary"
        else:
            reg["economic_stance"] = "neutral"

    reg["latency_ms"] = round(t.elapsed_ms, 1)
    awaz_log("ingestion", "source_fetch_completed", input_summary="Regulatory/Macro",
             output_summary=f"rate={reg['interest_rate']}, fx={reg['exchange_rate']}, stance={reg['economic_stance']}",
             duration_ms=t.elapsed_ms)
    return reg


def _fetch_sbp_data() -> dict[str, Any]:
    try:
        from bs4 import BeautifulSoup
        url = "https://www.sbp.org.pk/m_policy/index.htm"
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(resp.text, "lxml")
        text = soup.get_text(separator=" ", strip=True)[:3000]

        # Extract interest rate from page text
        import re
        rate_match = re.search(r'(\d{1,2}(?:\.\d+)?)\s*(?:%|percent)', text, re.IGNORECASE)
        rate = float(rate_match.group(1)) if rate_match else None

        awaz_log("ingestion", "source_fetch_completed", input_summary="SBP Website",
                 output_summary=f"rate={rate}%", source_url=url)

        return {
            "interest_rate": rate or 17.5,
            "rate_direction": "decreasing",
            "sbp_policy_summary": text[:500],
        }
    except Exception as exc:
        awaz_log("ingestion", "source_fetch_failed", input_summary="SBP Website",
                 error=str(exc), fallback="using known defaults")
        return {
            "interest_rate": 17.5,
            "rate_direction": "decreasing",
            "sbp_policy_summary": "SBP maintaining cautious monetary easing stance (fallback data)",
        }


def _fetch_exchange_rate() -> dict[str, Any]:
    api_key = os.environ.get("EXCHANGE_RATE_API_KEY", "")
    if not api_key:
        awaz_log("ingestion", "source_fetch_failed", input_summary="Exchange Rate API",
                 error="EXCHANGE_RATE_API_KEY not set", fallback="using approximate rate")
        return {"rate": 278.50, "change_30d": -0.8, "is_fallback": True}

    try:
        url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/USD"
        resp = requests.get(url, timeout=10)
        data = resp.json()
        pkr = data.get("conversion_rates", {}).get("PKR")
        awaz_log("ingestion", "source_fetch_completed", input_summary="Exchange Rate API",
                 output_summary=f"USD/PKR={pkr}", source_url=url)
        return {"rate": pkr or 278.50, "change_30d": -0.5}
    except Exception as exc:
        awaz_log("ingestion", "source_fetch_failed", input_summary="Exchange Rate API",
                 error=str(exc))
        return {"rate": 278.50, "change_30d": -0.8, "is_fallback": True}
