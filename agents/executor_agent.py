# agents/executor_agent.py
# Awaz Agent 4 — Executor (repurposed from Marketing agent)
# Simulates execution of action chain with failure recovery.

from __future__ import annotations
import json, os, time, traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from google import genai
from message_bus import send_message, receive_messages
from awaz_logger import awaz_log, LogTimer
import db

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output"


class ExecutorAgent:
    def __init__(self):
        self.client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))
        self.agent_name = "executor"
        self.pipeline_run_id = None
        OUTPUT_DIR.mkdir(exist_ok=True)

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

    def run(self, pipeline_run_id: str = None) -> None:
        self.pipeline_run_id = pipeline_run_id
        messages = receive_messages(self.agent_name)
        if not messages:
            return
        for msg in messages:
            if msg["message_type"] == "task":
                self._execute_chain(msg["payload"], msg["message_id"])

    def _execute_chain(self, payload: dict, parent_id: str) -> None:
        chain = payload.get("action_chain", [])
        intent = payload.get("intent", {})
        verdict = payload.get("verdict", "")
        execution_log = []

        awaz_log(self.agent_name, "execution_chain_started",
                 input_summary=f"{len(chain)} actions, verdict={verdict}")

        with LogTimer() as total_t:
            for i, action in enumerate(chain):
                atype = action.get("type", "unknown")
                aname = action.get("name", f"Action {i}")
                awaz_log(self.agent_name, "execution_started",
                         input_summary=f"[{i}] {atype}: {aname}",
                         target_system=atype)

                with LogTimer() as at:
                    try:
                        if atype == "alert":
                            result = self._exec_alert(action, intent, verdict)
                        elif atype in ("proceed", "hedge"):
                            result = self._exec_portfolio(action, intent)
                        elif atype == "investigate":
                            result = self._exec_investigate(action, intent)
                        elif atype == "halt":
                            result = self._exec_halt(action, intent)
                        elif atype == "monitor":
                            result = self._exec_monitor(action, intent)
                        else:
                            result = {"status": "skipped", "reason": f"Unknown type: {atype}"}

                        # Deliberate failure on 3rd action (index 2)
                        if i == 2:
                            result = self._exec_with_failure(action, intent, result)

                        awaz_log(self.agent_name, "execution_completed",
                                 input_summary=f"[{i}] {aname}",
                                 output_summary=f"status={result.get('status', '?')}",
                                 duration_ms=at.elapsed_ms)
                    except Exception as exc:
                        tb = traceback.format_exc()
                        awaz_log(self.agent_name, "execution_failed",
                                 input_summary=f"[{i}] {aname}",
                                 error=str(exc), stack_trace=tb)
                        result = {"status": "failed", "error": str(exc)}

                result["action_index"] = i
                result["action_name"] = aname
                result["action_type"] = atype
                result["duration_ms"] = round(at.elapsed_ms, 1)
                execution_log.append(result)

        awaz_log(self.agent_name, "execution_chain_completed",
                 output_summary=f"{len(execution_log)} actions executed",
                 duration_ms=total_t.elapsed_ms)

        send_message(
            from_agent=self.agent_name, to_agent="monitor", message_type="task",
            payload={
                "intent": intent,
                "verdict": verdict,
                "explanation": payload.get("explanation", ""),
                "action_chain": chain,
                "execution_log": execution_log,
                "source_scores": payload.get("source_scores", {}),
                "analysis_payload": payload.get("analysis_payload", {}),
                "total_execution_ms": round(total_t.elapsed_ms, 1),
                "pipeline_run_id": self.pipeline_run_id,
            }, parent_id=parent_id)

    def _exec_alert(self, action: dict, intent: dict, verdict: str) -> dict:
        """Generate Slack Block Kit message and save to file."""
        blocks = {
            "blocks": [
                {"type": "header", "text": {"type": "plain_text",
                    "text": f"🔔 Awaz Alert: {action.get('name', 'Alert')}", "emoji": True}},
                {"type": "section", "text": {"type": "mrkdwn",
                    "text": f"*Verdict:* {verdict}\n*Sector:* {intent.get('sector', 'N/A')}\n"
                            f"*Claim:* {intent.get('claim', 'N/A')[:200]}"}},
                {"type": "section", "text": {"type": "mrkdwn",
                    "text": f"*Action:* {action.get('description', 'Review required')}"}},
                {"type": "context", "elements": [{"type": "mrkdwn",
                    "text": f"Urgency: {action.get('urgency', 'medium')} | "
                            f"Generated by Awaz Intelligence Pipeline"}]},
            ]
        }
        path = OUTPUT_DIR / "slack-simulation.json"
        path.write_text(json.dumps(blocks, indent=2), encoding="utf-8")

        # Try webhook if configured
        webhook = os.environ.get("SLACK_WEBHOOK_URL", "")
        webhook_sent = False
        if webhook:
            try:
                import requests
                r = requests.post(webhook, json=blocks, timeout=10)
                webhook_sent = r.status_code == 200
            except Exception:
                pass

        awaz_log(self.agent_name, "alert_sent",
                 output_summary=f"Slack Block Kit saved, webhook={'sent' if webhook_sent else 'skipped'}")
        return {"status": "completed", "type": "alert", "file": str(path), "webhook_sent": webhook_sent}

    def _exec_portfolio(self, action: dict, intent: dict) -> dict:
        """Write portfolio/inventory transaction to SQLite."""
        before = {"allocation": "0%", "risk_score": 5.0, "sector": intent.get("sector", "general")}
        constraint = action.get("constraint", {})
        budget = constraint.get("value", 50000) if isinstance(constraint.get("value"), (int, float)) else 50000

        if action.get("type") == "proceed":
            after = {"allocation": f"{min(budget/1000, 15):.1f}%", "risk_score": 6.5,
                     "sector": intent.get("sector", "general"), "amount_invested": budget}
        else:  # hedge
            after = {"allocation": "hedged", "risk_score": 3.5,
                     "sector": intent.get("sector", "general"), "hedge_amount": budget}

        if self.pipeline_run_id:
            db.write_transaction(self.pipeline_run_id, action.get("type", "proceed"),
                                action.get("name", ""), before, after)

        awaz_log(self.agent_name, "state_change",
                 input_summary=f"before={json.dumps(before)[:100]}",
                 output_summary=f"after={json.dumps(after)[:100]}")
        return {"status": "completed", "type": action.get("type"), "before": before, "after": after}

    def _exec_investigate(self, action: dict, intent: dict) -> dict:
        """Fire additional targeted NewsAPI query."""
        from sources.news_fetcher import fetch_news
        keywords = [intent.get("sector", "market"), "analysis", "outlook"]
        results = fetch_news(keywords)
        report = {
            "investigation_target": action.get("name", ""),
            "query_keywords": keywords,
            "articles_found": len(results.get("articles", [])),
            "top_articles": results.get("articles", [])[:5],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        path = OUTPUT_DIR / "investigation-report.json"
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")

        awaz_log(self.agent_name, "investigation_completed",
                 output_summary=f"{report['articles_found']} articles, saved to {path}")
        return {"status": "completed", "type": "investigate", "file": str(path),
                "articles_found": report["articles_found"]}

    def _exec_halt(self, action: dict, intent: dict) -> dict:
        """Write hold record + email draft."""
        if self.pipeline_run_id:
            db.write_hold_record(self.pipeline_run_id, action.get("name", ""),
                                action.get("description", "Halted due to contradicting evidence"))

        email = (f"Subject: ACTION HOLD - {intent.get('sector', 'Sector')} Investment\n\n"
                 f"Dear Team,\n\nThis is to inform you that the planned action "
                 f"'{intent.get('action_suggested', 'action')}' in the {intent.get('sector', '')} "
                 f"sector has been placed on hold.\n\nReason: {action.get('description', '')}\n\n"
                 f"Please do not proceed until further analysis is complete.\n\n"
                 f"- Awaz Intelligence Pipeline\n"
                 f"Generated: {datetime.now(timezone.utc).isoformat()}")
        path = OUTPUT_DIR / "email-draft.txt"
        path.write_text(email, encoding="utf-8")

        awaz_log(self.agent_name, "halt_executed",
                 output_summary=f"Hold record + email draft saved")
        return {"status": "completed", "type": "halt", "file": str(path)}

    def _exec_monitor(self, action: dict, intent: dict) -> dict:
        """Write scheduled checks file."""
        next_check = datetime.now(timezone.utc) + timedelta(hours=24)
        checks = {
            "monitor_target": action.get("name", ""),
            "sector": intent.get("sector", ""),
            "next_check": next_check.isoformat(),
            "frequency": "daily",
            "metrics_to_track": ["price_change", "news_sentiment", "volume"],
            "created": datetime.now(timezone.utc).isoformat(),
        }
        path = OUTPUT_DIR / "scheduled-checks.json"
        path.write_text(json.dumps(checks, indent=2), encoding="utf-8")

        awaz_log(self.agent_name, "monitor_scheduled",
                 output_summary=f"Next check: {next_check.isoformat()}")
        return {"status": "completed", "type": "monitor", "file": str(path),
                "next_check": next_check.isoformat()}

    def _exec_with_failure(self, action: dict, intent: dict, original_result: dict) -> dict:
        """Deliberately fail via mock server, then retry with exponential backoff."""
        import requests as req

        awaz_log(self.agent_name, "execution_started",
                 input_summary="Mock API call (deliberate failure test)",
                 target_system="http://127.0.0.1:5001")

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                r = req.post("http://127.0.0.1:5001/api/internal/execute",
                            json={"action": action.get("name", "")}, timeout=5)
                if r.status_code == 200:
                    awaz_log(self.agent_name, "retry_succeeded",
                             input_summary=f"attempt {attempt}",
                             output_summary="Mock API returned 200")
                    return original_result
                else:
                    raise Exception(f"Mock API returned {r.status_code}: {r.text}")
            except Exception as exc:
                backoff = 2 ** attempt * 0.1  # 0.2s, 0.4s, 0.8s
                awaz_log(self.agent_name, "execution_failed",
                         input_summary=f"attempt {attempt}/{max_retries}",
                         error=str(exc), stack_trace=traceback.format_exc() if attempt == 1 else None)
                awaz_log(self.agent_name, "retry_attempted",
                         input_summary=f"attempt {attempt+1}, backoff={backoff:.1f}s")
                time.sleep(backoff)

        # All retries failed — ask Gemini for fallback
        awaz_log(self.agent_name, "fallback_reasoning_started",
                 input_summary=f"All {max_retries} retries failed for {action.get('name', '')}")

        fallback_reasoning = self._call_gemini(
            "You are deciding the best fallback action when a primary action fails. Be concise.",
            f"The action '{action.get('name', '')}' failed after {max_retries} retries. "
            f"Sector: {intent.get('sector', '')}. What is the best alternative? "
            "Return JSON: {\"fallback_action\": \"...\", \"reasoning\": \"...\"}")

        awaz_log(self.agent_name, "fallback_action_taken",
                 output_summary=fallback_reasoning[:200],
                 reason="All retries exhausted")

        original_result["had_failure"] = True
        original_result["failure_recovery"] = "fallback_executed"
        original_result["fallback_reasoning"] = fallback_reasoning[:300]
        return original_result
