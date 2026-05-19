# sources/reddit_fetcher.py
# Awaz — Reddit sentiment fetcher via PRAW.

from __future__ import annotations
import os
from typing import Any
from awaz_logger import awaz_log, LogTimer

SUBREDDITS = ["investing", "stocks", "worldnews", "pakistan"]


def fetch_reddit_sentiment(keywords: list[str]) -> dict[str, Any]:
    cid = os.environ.get("REDDIT_CLIENT_ID", "")
    csec = os.environ.get("REDDIT_CLIENT_SECRET", "")
    ua = os.environ.get("REDDIT_USER_AGENT", "awaz/1.0")

    if not cid or not csec:
        awaz_log("ingestion", "source_fetch_failed", input_summary="Reddit",
                 error="Reddit credentials not set — using fallback")
        return _fallback(keywords)

    awaz_log("ingestion", "source_fetch_started", input_summary="Reddit",
             output_summary=f"keywords={keywords}")

    all_posts = []
    sub_stats = {}
    with LogTimer() as t:
        try:
            import praw
            reddit = praw.Reddit(client_id=cid, client_secret=csec, user_agent=ua)
            query = " OR ".join(keywords)
            for sn in SUBREDDITS:
                try:
                    posts = list(reddit.subreddit(sn).search(query, sort="relevance", time_filter="week", limit=10))
                    sp = [{"title": p.title, "score": p.score, "num_comments": p.num_comments,
                           "subreddit": sn, "created_utc": p.created_utc} for p in posts]
                    all_posts.extend(sp)
                    sub_stats[sn] = len(sp)
                except Exception as e:
                    sub_stats[sn] = 0
        except Exception as exc:
            awaz_log("ingestion", "source_fetch_failed", input_summary="Reddit", error=str(exc))
            return _fallback(keywords)

    all_posts.sort(key=lambda p: p["score"], reverse=True)
    top = all_posts[:30]
    awaz_log("ingestion", "source_fetch_completed", input_summary="Reddit",
             output_summary=f"{len(top)} posts", duration_ms=t.elapsed_ms)
    return {"source": "Reddit", "posts": top, "total_posts": len(top),
            "subreddits_queried": SUBREDDITS, "subreddit_stats": sub_stats,
            "keywords_used": keywords, "latency_ms": round(t.elapsed_ms, 1)}


def _fallback(keywords: list[str]) -> dict[str, Any]:
    kw = keywords[0] if keywords else "market"
    posts = [
        {"title": f"Mixed signals on {kw} - analysts divided", "score": 245, "subreddit": "investing", "sentiment_hint": "neutral"},
        {"title": f"{kw} sector showing weakness - bearish divergence", "score": 182, "subreddit": "stocks", "sentiment_hint": "bearish"},
        {"title": f"Pakistan {kw} faces headwinds from global slowdown", "score": 127, "subreddit": "pakistan", "sentiment_hint": "bearish"},
        {"title": f"Long term bullish on {kw} fundamentals", "score": 98, "subreddit": "investing", "sentiment_hint": "bullish"},
        {"title": f"OPEC decisions could impact {kw} prices", "score": 76, "subreddit": "worldnews", "sentiment_hint": "neutral"},
    ]
    return {"source": "Reddit (simulated)", "posts": posts, "total_posts": len(posts),
            "subreddits_queried": SUBREDDITS, "keywords_used": keywords, "latency_ms": 0, "is_fallback": True}
