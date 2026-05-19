# sources/market_fetcher.py
#
# Awaz — Yahoo Finance market data fetcher via yfinance.
# Pulls 30-day historical price data and computes metrics.

from __future__ import annotations

import os
from typing import Any

import numpy as np

from awaz_logger import awaz_log, LogTimer

# Sector → ticker mapping
SECTOR_TICKERS = {
    "oil": ["USO", "XOM", "CL=F"],
    "energy": ["XLE", "USO", "XOM"],
    "petroleum": ["USO", "XOM"],
    "gas": ["UNG", "XLE"],
    "textile": ["PAKT.KA", "FFC.KA", "XLY"],
    "textiles": ["PAKT.KA", "FFC.KA", "XLY"],
    "technology": ["QQQ", "XLK"],
    "tech": ["QQQ", "XLK"],
    "finance": ["XLF", "JPM"],
    "banking": ["XLF", "KBE"],
    "agriculture": ["DBA", "MOO"],
    "real estate": ["VNQ", "IYR"],
    "pharma": ["XLV", "IBB"],
    "crypto": ["BTC-USD", "ETH-USD"],
    "gold": ["GLD", "GC=F"],
}

DEFAULT_TICKER = "SPY"


def fetch_market_data(sector: str) -> dict[str, Any]:
    """
    Fetch 30-day historical price data for the most relevant ticker.

    Parameters
    ----------
    sector : business sector identified from user's claim

    Returns
    -------
    dict with: ticker, data_range, pct_change_30d, trend_7d, volatility, prices
    """
    sector_lower = sector.lower().strip()
    tickers = SECTOR_TICKERS.get(sector_lower, [DEFAULT_TICKER])
    ticker = tickers[0]

    awaz_log(
        "ingestion", "source_fetch_started",
        input_summary="Yahoo Finance",
        output_summary=f"sector={sector}, ticker={ticker}",
    )

    with LogTimer() as timer:
        try:
            import yfinance as yf
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1mo")

            if hist.empty:
                # Try alternative ticker
                if len(tickers) > 1:
                    ticker = tickers[1]
                    stock = yf.Ticker(ticker)
                    hist = stock.history(period="1mo")

                if hist.empty:
                    ticker = DEFAULT_TICKER
                    stock = yf.Ticker(ticker)
                    hist = stock.history(period="1mo")

        except Exception as exc:
            awaz_log(
                "ingestion", "source_fetch_failed",
                input_summary="Yahoo Finance",
                error=str(exc),
                fallback="using simulated data",
            )
            return _fallback_market(sector, ticker)

    if hist.empty:
        awaz_log(
            "ingestion", "source_fetch_failed",
            input_summary="Yahoo Finance",
            error="No historical data returned",
            duration_ms=timer.elapsed_ms,
        )
        return _fallback_market(sector, ticker)

    # Calculate metrics
    closes = hist["Close"].values
    pct_change_30d = float(((closes[-1] - closes[0]) / closes[0]) * 100) if len(closes) > 1 else 0.0

    # 7-day trend
    if len(closes) >= 7:
        last_7 = closes[-7:]
        trend_pct = float(((last_7[-1] - last_7[0]) / last_7[0]) * 100)
        if trend_pct > 1:
            trend_7d = "up"
        elif trend_pct < -1:
            trend_7d = "down"
        else:
            trend_7d = "flat"
    else:
        trend_7d = "insufficient_data"
        trend_pct = 0.0

    # Volatility (annualized std dev of daily returns)
    if len(closes) > 2:
        daily_returns = np.diff(closes) / closes[:-1]
        volatility = float(np.std(daily_returns) * np.sqrt(252) * 100)
    else:
        volatility = 0.0

    # Build price series for temporal analysis
    price_series = [
        {"date": str(d.date()), "close": round(float(p), 2)}
        for d, p in zip(hist.index, closes)
    ]

    data_range = f"{hist.index[0].date()} to {hist.index[-1].date()}" if len(hist) > 0 else "N/A"

    result = {
        "source": "Yahoo Finance",
        "ticker": ticker,
        "sector": sector,
        "data_range": data_range,
        "pct_change_30d": round(pct_change_30d, 2),
        "trend_7d": trend_7d,
        "trend_7d_pct": round(trend_pct, 2) if 'trend_pct' in dir() else 0,
        "volatility": round(volatility, 2),
        "latest_price": round(float(closes[-1]), 2),
        "price_series": price_series[-10:],  # last 10 data points for charting
        "latency_ms": round(timer.elapsed_ms, 1),
    }

    awaz_log(
        "ingestion", "source_fetch_completed",
        input_summary="Yahoo Finance",
        output_summary=f"ticker={ticker}, 30d={pct_change_30d:+.1f}%, 7d={trend_7d}, vol={volatility:.1f}%",
        duration_ms=timer.elapsed_ms,
        ticker=ticker,
        pct_change_30d=result["pct_change_30d"],
        trend_7d=trend_7d,
        volatility=result["volatility"],
    )

    return result


def _fallback_market(sector: str, ticker: str) -> dict[str, Any]:
    """Return simulated market data when yfinance fails."""
    return {
        "source": "Yahoo Finance (simulated fallback)",
        "ticker": ticker,
        "sector": sector,
        "data_range": "simulated",
        "pct_change_30d": -3.2,
        "trend_7d": "down",
        "trend_7d_pct": -1.8,
        "volatility": 22.5,
        "latest_price": 72.40,
        "price_series": [],
        "latency_ms": 0,
        "is_fallback": True,
    }
