# agents/analyst_agent.py
# Awaz Agent 2 — Analyst & Contradiction Detection (repurposed from Product agent)
# Compares user's claim against 4 data sources, detects contradictions,
# uses chain-of-thought reasoning, credibility scoring formula.

from __future__ import annotations
import json, os, time, math
from typing import Any
from google import genai
from message_bus import send_message, receive_messages
from awaz_logger import awaz_log, LogTimer

# Source weights for credibility formula
SOURCE_WEIGHTS = {
    "news": 0.16,
    "market": 0.16,
    "reddit": 0.13,
    "regulatory": 0.11,
    "business_recorder": 0.11,
    "psx": 0.11,
    "dawn_business": 0.11,
    "profit_pakistan": 0.11,
}


class AnalystAgent:
    def __init__(self):
        self.client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))
        self.agent_name = "analyst"

    def _call_gemini(self, system_prompt: str, user_prompt: str, retries: int = 1) -> str:
        for attempt in range(retries + 1):
            try:
                resp = self.client.models.generate_content(
                    model="gemini-2.5-flash", contents=user_prompt,
                    config=genai.types.GenerateContentConfig(system_instruction=system_prompt))
                return resp.text
            except Exception as exc:
                if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
                    return self._call_hf(system_prompt, user_prompt)
                if attempt < retries:
                    time.sleep(2)
                else:
                    raise

    def _call_hf(self, system_prompt: str, user_prompt: str) -> str:
        from huggingface_hub import InferenceClient
        try:
            c = InferenceClient(api_key=os.environ.get("HF_API_KEY", ""))
            r = c.chat_completion(model="meta-llama/Llama-3.3-70B-Instruct",
                messages=[{"role": "system", "content": system_prompt},
                          {"role": "user", "content": user_prompt}], max_tokens=4000)
            return r.choices[0].message.content or ""
        except Exception as exc:
            awaz_log(self.agent_name, "llm_fallback_failed", error=str(exc))
            return ""

    def run(self) -> None:
        messages = receive_messages(self.agent_name)
        if not messages:
            return
        for msg in messages:
            if msg["message_type"] == "task":
                self._analyze(msg["payload"], msg["message_id"])

    def _analyze(self, payload: dict, parent_id: str) -> None:
        intent = payload.get("intent", {})
        claim = intent.get("claim", "")
        sector = intent.get("sector", "")

        awaz_log(self.agent_name, "analysis_started",
                 input_summary=f"claim: {claim[:100]}", output_summary=f"sector: {sector}")

        with LogTimer() as total_t:
            # Analyze each source against the claim
            news_analysis = self._analyze_source("news", claim, payload.get("news_data", {}))
            market_analysis = self._analyze_source("market", claim, payload.get("market_data", {}))
            reddit_analysis = self._analyze_reddit(claim, payload.get("reddit_data", {}))
            regulatory_analysis = self._analyze_source("regulatory", claim, payload.get("regulatory_data", {}))
            business_recorder_analysis = self._analyze_source(
                "business_recorder", claim, payload.get("business_recorder_data", {})
            )
            psx_analysis = self._analyze_source("psx", claim, payload.get("psx_data", {}))
            dawn_business_analysis = self._analyze_source(
                "dawn_business", claim, payload.get("dawn_business_data", {})
            )
            profit_pakistan_analysis = self._analyze_source(
                "profit_pakistan", claim, payload.get("profit_pakistan_data", {})
            )

            # Temporal analysis on market data
            temporal = self._temporal_analysis(payload.get("market_data", {}))

            # Calculate credibility-weighted contradiction score
            source_scores = {
                "news": news_analysis.get("contradiction_score", 0.5),
                "market": market_analysis.get("contradiction_score", 0.5),
                "reddit": reddit_analysis.get("contradiction_score", 0.5),
                "regulatory": regulatory_analysis.get("contradiction_score", 0.5),
                "business_recorder": business_recorder_analysis.get("contradiction_score", 0.5),
                "psx": psx_analysis.get("contradiction_score", 0.5),
                "dawn_business": dawn_business_analysis.get("contradiction_score", 0.5),
                "profit_pakistan": profit_pakistan_analysis.get("contradiction_score", 0.5),
            }

            # Credibility formula: score = source_weight × age_decay × cross_source_consistency
            weighted_score = self._compute_credibility_score(source_scores)

            # Determine verdict
            if weighted_score < 0.35:
                verdict = "confirmed"
            elif weighted_score < 0.60:
                verdict = "partially_confirmed"
            else:
                verdict = "contradicted"

            # Count how many sources contradict
            contradicting = [s for s, sc in source_scores.items() if sc > 0.55]

            # Generate plain language explanation
            explanation = self._generate_explanation(
                claim, verdict, source_scores,
                news_analysis, market_analysis, reddit_analysis, regulatory_analysis,
                business_recorder_analysis, psx_analysis, dawn_business_analysis,
                profit_pakistan_analysis, temporal)

            source_evidence, source_reasoning = self._build_source_intelligence(payload, {
                "news": news_analysis,
                "market": market_analysis,
                "reddit": reddit_analysis,
                "regulatory": regulatory_analysis,
                "business_recorder": business_recorder_analysis,
                "psx": psx_analysis,
                "dawn_business": dawn_business_analysis,
                "profit_pakistan": profit_pakistan_analysis,
            })

        awaz_log(self.agent_name, "analysis_completed",
                 input_summary=claim[:80],
                 output_summary=f"verdict={verdict}, score={weighted_score:.2f}",
                 duration_ms=total_t.elapsed_ms, verdict=verdict,
                 contradiction_score=round(weighted_score, 3),
                 source_scores=source_scores,
                 source_evidence=source_evidence,
                 source_reasoning=source_reasoning)

        # Send to Strategist
        send_message(
            from_agent=self.agent_name, to_agent="strategist", message_type="task",
            payload={
                "intent": intent,
                "verdict": verdict,
                "confidence": round(1.0 - weighted_score, 2),
                "weighted_contradiction_score": round(weighted_score, 3),
                "source_scores": source_scores,
                "contradicting_sources": contradicting,
                "news_analysis": news_analysis,
                "market_analysis": market_analysis,
                "reddit_analysis": reddit_analysis,
                "regulatory_analysis": regulatory_analysis,
                "business_recorder_analysis": business_recorder_analysis,
                "psx_analysis": psx_analysis,
                "dawn_business_analysis": dawn_business_analysis,
                "profit_pakistan_analysis": profit_pakistan_analysis,
                "temporal_analysis": temporal,
                "explanation": explanation,
                "source_evidence": source_evidence,
                "source_reasoning": source_reasoning,
                "original_payload": payload,
            }, parent_id=parent_id)

    def _analyze_source(self, source_name: str, claim: str, data: dict) -> dict:
        awaz_log(self.agent_name, "contradiction_detection_started",
                 input_summary=f"{source_name} vs claim")

        sys_prompt = (
            "You are an analytical AI performing contradiction detection. "
            "Think step by step through the evidence before reaching a conclusion. "
            "Use chain-of-thought reasoning.\n\n"
            "Return ONLY valid JSON with NO markdown:\n"
            '{"reasoning_chain": ["step 1...", "step 2...", "step 3..."], '
            '"contradiction_score": 0.0 to 1.0 where 0=fully supports and 1=fully contradicts, '
            '"summary": "one sentence summary of finding"}'
        )
        data_summary = json.dumps(data, default=str)[:2000]
        user_prompt = (
            f"CLAIM: {claim}\n\n"
            f"DATA SOURCE ({source_name}):\n{data_summary}\n\n"
            "Does this data support or contradict the claim? Think step by step."
        )

        with LogTimer() as t:
            raw = self._call_gemini(sys_prompt, user_prompt)

        try:
            clean = raw.strip().strip("```json").strip("```").strip()
            result = json.loads(clean)
        except json.JSONDecodeError:
            result = {"reasoning_chain": [raw[:300]], "contradiction_score": 0.5,
                      "summary": "Analysis inconclusive"}

        score = float(result.get("contradiction_score", 0.5))
        score = max(0.0, min(1.0, score))
        result["contradiction_score"] = score

        if score > 0.55:
            awaz_log(self.agent_name, "contradiction_detected",
                     input_summary=f"{source_name}: score={score:.2f}",
                     output_summary=result.get("summary", "")[:150],
                     duration_ms=t.elapsed_ms)
        else:
            awaz_log(self.agent_name, "no_contradiction_found",
                     input_summary=f"{source_name}: score={score:.2f}",
                     output_summary=result.get("summary", "")[:150],
                     duration_ms=t.elapsed_ms)

        return result

    def _analyze_reddit(self, claim: str, data: dict) -> dict:
        """Special Reddit analysis: classify each post sentiment then aggregate."""
        posts = data.get("posts", [])
        if not posts:
            return {"contradiction_score": 0.5, "aggregate_sentiment": 0.0,
                    "summary": "No Reddit data available", "reasoning_chain": []}

        titles = [p.get("title", "") for p in posts[:15]]
        sys_prompt = (
            "Classify each post title as bullish (+1), bearish (-1), or neutral (0) "
            "relative to the given claim. Use chain-of-thought reasoning.\n"
            "Return ONLY valid JSON:\n"
            '{"classifications": [{"title": "...", "sentiment": 1 or -1 or 0}], '
            '"aggregate_score": -1.0 to 1.0, "contradiction_score": 0.0 to 1.0, '
            '"reasoning_chain": ["step1", "step2"], "summary": "..."}'
        )
        user_prompt = f"CLAIM: {claim}\n\nPost titles:\n" + "\n".join(f"- {t}" for t in titles)

        with LogTimer() as t:
            raw = self._call_gemini(sys_prompt, user_prompt)

        try:
            clean = raw.strip().strip("```json").strip("```").strip()
            result = json.loads(clean)
        except json.JSONDecodeError:
            result = {"classifications": [], "aggregate_score": 0.0,
                      "contradiction_score": 0.5, "reasoning_chain": [raw[:200]],
                      "summary": "Reddit analysis parse failed"}

        result["evidence"] = result.get("summary", "")

        awaz_log(self.agent_name, "reddit_sentiment_analyzed",
                 input_summary=f"{len(titles)} posts",
                 output_summary=f"agg={result.get('aggregate_score', 0)}, "
                               f"contra={result.get('contradiction_score', 0.5)}",
                 duration_ms=t.elapsed_ms)
        return result

    def _build_source_intelligence(self, payload: dict, analyses: dict[str, dict]) -> tuple[dict[str, str], dict[str, str]]:
        source_payload_map = {
            "news": payload.get("news_data", {}),
            "market": payload.get("market_data", {}),
            "reddit": payload.get("reddit_data", {}),
            "regulatory": payload.get("regulatory_data", {}),
            "business_recorder": payload.get("business_recorder_data", {}),
            "psx": payload.get("psx_data", {}),
            "dawn_business": payload.get("dawn_business_data", {}),
            "profit_pakistan": payload.get("profit_pakistan_data", {}),
        }
        source_evidence: dict[str, str] = {}
        source_reasoning: dict[str, str] = {}

        for key, analysis in analyses.items():
            source_evidence[key] = self._clip(
                str(analysis.get("summary") or self._extract_payload_hint(source_payload_map.get(key, {})))
            )
            reasoning_chain = analysis.get("reasoning_chain") or []
            if isinstance(reasoning_chain, list):
                source_reasoning[key] = self._clip(" | ".join(str(r) for r in reasoning_chain if str(r).strip()))
            else:
                source_reasoning[key] = self._clip(str(reasoning_chain))

        return source_evidence, source_reasoning

    def _extract_payload_hint(self, data: dict) -> str:
        if not isinstance(data, dict) or not data:
            return "No source evidence available."
        if "summary" in data and data.get("summary"):
            return str(data.get("summary"))
        if "headlines" in data and isinstance(data.get("headlines"), list):
            headline = data["headlines"][0] if data["headlines"] else {}
            if isinstance(headline, dict):
                return str(headline.get("summary") or headline.get("title") or "")
        if "articles" in data and isinstance(data.get("articles"), list):
            article = data["articles"][0] if data["articles"] else {}
            if isinstance(article, dict):
                return str(article.get("description") or article.get("title") or "")
        if "posts" in data and isinstance(data.get("posts"), list):
            post = data["posts"][0] if data["posts"] else {}
            if isinstance(post, dict):
                return str(post.get("title") or "")
        return "No source evidence available."

    def _clip(self, text: str, limit: int = 260) -> str:
        clean = " ".join(text.split())
        if len(clean) <= limit:
            return clean
        return clean[: limit - 3] + "..."

    def _temporal_analysis(self, market_data: dict) -> dict:
        """Detect if market trend is accelerating or reversing."""
        prices = market_data.get("price_series", [])
        if len(prices) < 5:
            return {"trend_momentum": "insufficient_data", "acceleration": 0}

        closes = [p["close"] for p in prices]
        # Simple momentum: compare first half avg vs second half avg
        mid = len(closes) // 2
        first_half_avg = sum(closes[:mid]) / mid
        second_half_avg = sum(closes[mid:]) / (len(closes) - mid)
        accel = (second_half_avg - first_half_avg) / first_half_avg * 100

        if accel > 1.5:
            momentum = "accelerating_up"
        elif accel < -1.5:
            momentum = "accelerating_down"
        else:
            momentum = "stable"

        awaz_log(self.agent_name, "temporal_analysis_completed",
                 output_summary=f"momentum={momentum}, accel={accel:.2f}%")
        return {"trend_momentum": momentum, "acceleration": round(accel, 2)}

    def _compute_credibility_score(self, source_scores: dict) -> float:
        """Credibility formula: weighted score with cross-source consistency bonus."""
        weighted = sum(SOURCE_WEIGHTS.get(s, 0.25) * sc for s, sc in source_scores.items())

        # Cross-source consistency: if sources agree, boost confidence in that direction
        scores = list(source_scores.values())
        variance = sum((s - sum(scores)/len(scores))**2 for s in scores) / len(scores)
        consistency_factor = 1.0 + (0.2 * (1.0 - min(variance * 4, 1.0)))

        # Age decay: not applicable here since all data is fresh, factor = 1.0
        final = weighted * consistency_factor
        return max(0.0, min(1.0, final))

    def _generate_explanation(
        self,
        claim,
        verdict,
        scores,
        news_a,
        market_a,
        reddit_a,
        reg_a,
        br_a,
        psx_a,
        dawn_a,
        profit_a,
        temporal,
    ) -> str:
        sys_prompt = (
            "You are explaining a financial analysis to a Pakistani business owner in simple, "
            "conversational language. No jargon. Be direct and clear. 3-4 sentences max."
        )
        user_prompt = (
            f"The boss claimed: \"{claim}\"\n"
            f"Our verdict: {verdict}\n"
            f"News analysis: {news_a.get('summary', 'N/A')}\n"
            f"Market data: {market_a.get('summary', 'N/A')}\n"
            f"Reddit sentiment: {reddit_a.get('summary', 'N/A')}\n"
            f"Regulatory context: {reg_a.get('summary', 'N/A')}\n"
            f"Business Recorder: {br_a.get('summary', 'N/A')}\n"
            f"PSX snapshot: {psx_a.get('summary', 'N/A')}\n"
            f"Dawn Business: {dawn_a.get('summary', 'N/A')}\n"
            f"Profit Pakistan: {profit_a.get('summary', 'N/A')}\n"
            f"Market momentum: {temporal.get('trend_momentum', 'N/A')}\n\n"
            "Explain this verdict in plain conversational English."
        )
        return self._call_gemini(sys_prompt, user_prompt)
