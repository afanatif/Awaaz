# agents/monitor_agent.py
# Awaz Agent 5 — Monitor & Outcome (repurposed from QA agent)
# Computes final outcome, before/after metrics, estimates tokens,
# generates bilingual summary, and saves outcome.json.

from __future__ import annotations
import json, os, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from google import genai
from message_bus import send_message, receive_messages
from awaz_logger import awaz_log, LogTimer
import db

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output"


class MonitorAgent:
    def __init__(self):
        self.client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))
        self.agent_name = "monitor"

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
                self._compute_outcome(msg["payload"], msg["message_id"])

    def _compute_outcome(self, payload: dict, parent_id: str) -> None:
        intent = payload.get("intent", {})
        verdict = payload.get("verdict", "")
        exec_log = payload.get("execution_log", [])
        total_exec_ms = payload.get("total_execution_ms", 0)
        pipeline_run_id = payload.get("pipeline_run_id")

        awaz_log(self.agent_name, "outcome_computation_started",
                 input_summary=f"verdict={verdict}, executions={len(exec_log)}")

        with LogTimer() as t:
            # Gather before/after metrics
            metrics = self._compute_metrics(exec_log)

            # Estimate token usage
            tokens = self._estimate_tokens(payload)

            # Generate bilingual summary
            summary_en, summary_ur = self._generate_summaries(intent, verdict, metrics)

            outcome = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "pipeline_run_id": pipeline_run_id,
                "input": {
                    "claim": intent.get("claim", ""),
                    "sector": intent.get("sector", ""),
                },
                "verdict": verdict,
                "confidence": payload.get("analysis_payload", {}).get("confidence", 0.0),
                "metrics_changed": metrics,
                "execution_summary": {
                    "total_actions": len(exec_log),
                    "completed": sum(1 for e in exec_log if e.get("status") == "completed"),
                    "failed": sum(1 for e in exec_log if e.get("status") == "failed"),
                    "had_recovery": any(e.get("had_failure") for e in exec_log),
                },
                "latency_summary": {
                    "ingestion_ms": payload.get("analysis_payload", {}).get("original_payload", {}).get("total_ingestion_ms", 0),
                    "execution_ms": total_exec_ms,
                    "monitor_ms": 0, # updated below
                },
                "token_estimate": tokens,
                "summary_en": summary_en,
                "summary_ur": summary_ur,
            }

            if pipeline_run_id:
                # Calculate total latency up to this point
                # (Actual total will include monitor_ms, but we need to pass a number)
                db.complete_pipeline_run(pipeline_run_id, verdict, 0) # Total latency updated by main orchestrator

        outcome["latency_summary"]["monitor_ms"] = round(t.elapsed_ms, 1)

        # Save outcome to file
        OUTPUT_DIR.mkdir(exist_ok=True)
        path = OUTPUT_DIR / "outcome.json"
        path.write_text(json.dumps(outcome, indent=2), encoding="utf-8")

        awaz_log(self.agent_name, "outcome_computation_completed",
                 output_summary=f"Outcome saved to {path}",
                 duration_ms=t.elapsed_ms,
                 total_actions=outcome["execution_summary"]["total_actions"],
                 estimated_tokens=tokens)

        # Send final completion message to CEO (which in Awaz is just back to orchestrator)
        send_message(
            from_agent=self.agent_name, to_agent="system", message_type="result",
            payload={"outcome": outcome, "outcome_file": str(path)}, parent_id=parent_id)

    def _compute_metrics(self, exec_log: list[dict]) -> dict:
        """Extract before/after metrics from execution logs."""
        metrics = {
            "portfolio_allocation": {"before": "0%", "after": "0%"},
            "risk_score": {"before": 5.0, "after": 5.0},
            "alerts_sent": 0,
            "actions_attempted": len(exec_log),
        }

        for log in exec_log:
            if log.get("type") in ("proceed", "hedge") and "before" in log and "after" in log:
                metrics["portfolio_allocation"]["before"] = log["before"].get("allocation", "0%")
                metrics["portfolio_allocation"]["after"] = log["after"].get("allocation", "0%")
                metrics["risk_score"]["before"] = log["before"].get("risk_score", 5.0)
                metrics["risk_score"]["after"] = log["after"].get("risk_score", 5.0)
            elif log.get("type") == "alert" and log.get("status") == "completed":
                metrics["alerts_sent"] += 1

        awaz_log(self.agent_name, "metrics_computed", output_summary=f"allocation {metrics['portfolio_allocation']['before']} -> {metrics['portfolio_allocation']['after']}")
        return metrics

    def _estimate_tokens(self, payload: dict) -> int:
        """Rough estimation of Gemini tokens used across all agents (1 token ~ 4 chars)."""
        text = json.dumps(payload, default=str)
        chars = len(text)
        # Factor in prompts and multiple agent passes
        estimated = int((chars / 4) * 2.5)
        return max(500, estimated)

    def _generate_summaries(self, intent: dict, verdict: str, metrics: dict) -> tuple[str, str]:
        """Generate plain language summaries in English and Urdu."""
        sys_prompt = "You are summarizing a business intelligence pipeline outcome. Write one paragraph in English, and its exact translation in Urdu (Arabic script, not Roman)."
        user_prompt = (
            f"The user wanted to: {intent.get('action_suggested', 'take action')} in {intent.get('sector', 'sector')}.\n"
            f"The pipeline verdict was: {verdict}.\n"
            f"As a result, portfolio allocation changed from {metrics['portfolio_allocation']['before']} to {metrics['portfolio_allocation']['after']}.\n"
            f"Risk score changed from {metrics['risk_score']['before']} to {metrics['risk_score']['after']}.\n"
            f"Write a short, professional summary of this outcome in English, followed by the Urdu translation."
            f"Return JSON: {{\"english\": \"...\", \"urdu\": \"...\"}}"
        )

        raw = self._call_gemini(sys_prompt, user_prompt)
        try:
            clean = raw.strip().strip("```json").strip("```").strip()
            res = json.loads(clean)
            en = res.get("english", "Analysis complete.")
            ur = res.get("urdu", "تجزیہ مکمل ہو گیا۔")
        except Exception:
            en = f"Pipeline analysis for {intent.get('sector', 'sector')} resulted in a {verdict} verdict. Actions were executed accordingly."
            ur = f"پائپ لائن کا تجزیہ {verdict} کے نتیجے پر پہنچا۔"

        awaz_log(self.agent_name, "bilingual_summary_generated", output_summary=f"EN: {en[:50]}... UR: {ur[:50]}...")
        return en, ur
