# agents/strategist_agent.py
# Awaz Agent 3 — Strategist (repurposed from Engineer agent)
# Generates 3-5 constrained actions based on verdict, evaluates feasibility.

from __future__ import annotations
import json, os, time
from typing import Any
from google import genai
from message_bus import send_message, receive_messages
from awaz_logger import awaz_log, LogTimer


class StrategistAgent:
    def __init__(self):
        self.client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))
        self.agent_name = "strategist"

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
                self._strategize(msg["payload"], msg["message_id"])

    def _strategize(self, payload: dict, parent_id: str) -> None:
        verdict = payload.get("verdict", "partially_confirmed")
        intent = payload.get("intent", {})
        claim = intent.get("claim", "")
        explanation = payload.get("explanation", "")

        awaz_log(self.agent_name, "strategy_generation_started",
                 input_summary=f"verdict={verdict}, claim={claim[:80]}")

        with LogTimer() as t:
            # Generate actions via Gemini
            actions = self._generate_actions(verdict, intent, explanation, payload)

            # Evaluate constraints on each action
            evaluated = self._evaluate_constraints(actions)

            # Order into dependency chain
            chain = self._build_chain(evaluated)

            # Build strategist reasoning for each action
            strategist_reasoning = self._build_strategist_reasoning(verdict, intent, explanation, chain, payload)

        awaz_log(self.agent_name, "strategy_generation_completed",
                 output_summary=f"{len(chain)} actions in chain",
                 duration_ms=t.elapsed_ms)

        send_message(
            from_agent=self.agent_name, to_agent="executor", message_type="task",
            payload={
                "intent": intent,
                "verdict": verdict,
                "explanation": explanation,
                "action_chain": chain,
                "strategist_reasoning": strategist_reasoning,
                "source_scores": payload.get("source_scores", {}),
                "analysis_payload": payload,
            }, parent_id=parent_id)

    def _generate_actions(self, verdict: str, intent: dict, explanation: str, full_payload: dict) -> list[dict]:
        sys_prompt = (
            "You are a strategic business advisor generating an action plan. "
            "Generate exactly 4 actions based on the verdict.\n"
            "If verdict is 'confirmed': actions should be execution-oriented (proceed with plan).\n"
            "If verdict is 'contradicted': actions should be protective (halt, hedge, investigate).\n"
            "If 'partially_confirmed': mix of cautious execution and investigation.\n\n"
            "Each action MUST have:\n"
            "- name: descriptive short name\n"
            "- type: one of [proceed, halt, hedge, investigate, alert, monitor]\n"
            "- description: what to do\n"
            "- constraint: {type: 'budget'|'time_window'|'urgency'|'dependency', value: ..., limit: ...}\n"
            "- urgency: low|medium|high\n"
            "- depends_on: null or index of previous action (0-based)\n\n"
            "IMPORTANT: One action must be of type 'alert' (to notify stakeholders).\n"
            "One action must be of type 'monitor' (for follow-up).\n"
            "Return ONLY a JSON array. No markdown."
        )

        market = full_payload.get("market_analysis", {})
        scores = full_payload.get("source_scores", {})

        user_prompt = (
            f"Verdict: {verdict}\n"
            f"Claim: {intent.get('claim', '')}\n"
            f"Sector: {intent.get('sector', '')}\n"
            f"Suggested action: {intent.get('action_suggested', '')}\n"
            f"Explanation: {explanation[:500]}\n"
            f"Source contradiction scores: {json.dumps(scores)}\n"
            f"Market trend: {market.get('summary', 'N/A')}\n\n"
            "Generate exactly 4 actions as a JSON array."
        )

        raw = self._call_gemini(sys_prompt, user_prompt)
        try:
            clean = raw.strip().strip("```json").strip("```").strip()
            actions = json.loads(clean)
            if not isinstance(actions, list):
                actions = [actions]
        except json.JSONDecodeError:
            awaz_log(self.agent_name, "action_generation_parse_failed", error=raw[:200])
            actions = self._fallback_actions(verdict, intent)

        # Log each generated action
        for i, action in enumerate(actions):
            awaz_log(self.agent_name, "action_generated",
                     output_summary=f"[{i}] {action.get('type','?')}: {action.get('name','?')}",
                     action_type=action.get("type"), action_name=action.get("name"))

        return actions

    def _evaluate_constraints(self, actions: list[dict]) -> list[dict]:
        """Evaluate each action's constraint and reject/modify infeasible ones."""
        evaluated = []
        for i, action in enumerate(actions):
            constraint = action.get("constraint", {})
            c_type = constraint.get("type", "none")
            feasible = True
            reason = ""

            if c_type == "budget":
                limit = constraint.get("limit", 100000)
                value = constraint.get("value", 0)
                if isinstance(value, (int, float)) and isinstance(limit, (int, float)):
                    if value > limit:
                        feasible = False
                        reason = f"Budget {value} exceeds limit {limit}"
                        action["constraint"]["value"] = limit
                        action["modified"] = True

            elif c_type == "time_window":
                # All time windows are feasible for simulation
                pass

            elif c_type == "dependency":
                dep = action.get("depends_on")
                if dep is not None and dep >= i:
                    feasible = False
                    reason = f"Circular dependency: action {i} depends on {dep}"
                    action["depends_on"] = None

            action["constraint_evaluated"] = True
            action["constraint_feasible"] = feasible
            action["constraint_reason"] = reason

            awaz_log(self.agent_name, "constraint_evaluated",
                     input_summary=f"action={action.get('name','?')}, type={c_type}",
                     output_summary=f"feasible={feasible}" + (f", reason={reason}" if reason else ""))

            if not feasible:
                awaz_log(self.agent_name, "action_modified",
                         input_summary=action.get("name", "?"),
                         output_summary=reason)

            evaluated.append(action)
        return evaluated

    def _build_chain(self, actions: list[dict]) -> list[dict]:
        """Order actions into a dependency chain."""
        for i, action in enumerate(actions):
            action["chain_index"] = i
            if i > 0 and action.get("depends_on") is None:
                action["depends_on"] = i - 1
        return actions

    def _build_strategist_reasoning(self, verdict: str, intent: dict, explanation: str, chain: list[dict], full_payload: dict) -> dict:
        """Build detailed reasoning for each action: what, why, based on what, should_execute."""
        claim = intent.get("claim", "")
        sector = intent.get("sector", "")
        source_scores = full_payload.get("source_scores", {})

        reasoning_by_action = {}
        for i, action in enumerate(chain):
            atype = action.get("type", "")
            aname = action.get("name", "")
            desc = action.get("description", "")

            # Determine if action should be executed
            should_execute = self._should_execute_action(verdict, atype)

            # Build contextual reasoning
            what = f"Execute action: {aname} ({atype}). {desc}"
            
            why_parts = []
            if verdict == "contradicted":
                why_parts.append(f"Verdict is CONTRADICTED for claim about {sector}.")
                why_parts.append("Contradicting evidence suggests caution is required.")
            elif verdict == "confirmed":
                why_parts.append(f"Verdict is CONFIRMED for claim about {sector}.")
                why_parts.append("Supporting evidence enables forward execution.")
            else:
                why_parts.append(f"Verdict is PARTIALLY CONFIRMED for claim about {sector}.")
                why_parts.append("Mixed evidence suggests balanced approach.")

            # Add action-specific rationale
            if atype == "halt":
                why_parts.append("Halting prevents exposure to contradicted risks.")
            elif atype == "investigate":
                why_parts.append("Investigation clarifies ambiguous signals and reduces uncertainty.")
            elif atype == "alert":
                why_parts.append("Alerting stakeholders ensures transparency and rapid response.")
            elif atype == "monitor":
                why_parts.append("Monitoring tracks evolving conditions for timely adjustments.")
            elif atype == "proceed":
                why_parts.append("Proceeding capitalizes on confirmed opportunity.")
            elif atype == "hedge":
                why_parts.append("Hedging mitigates downside while preserving upside.")

            why = " ".join(why_parts)

            # "Based on what" — reference key sources
            based_on_parts = []
            high_contra = [k for k, v in source_scores.items() if v > 0.6]
            high_support = [k for k, v in source_scores.items() if v < 0.4]

            if high_contra:
                based_on_parts.append(f"Contradiction signals from: {', '.join(high_contra)}")
            if high_support:
                based_on_parts.append(f"Support signals from: {', '.join(high_support)}")
            
            if not based_on_parts:
                based_on_parts.append("Overall weighted contradiction score and source evidence")

            based_on = "Based on: " + "; ".join(based_on_parts) + "."

            reasoning_by_action[f"action_{i}"] = {
                "should_execute": should_execute,
                "what": what,
                "why": why,
                "based_on": based_on,
                "action_type": atype,
                "action_name": aname,
            }

        return reasoning_by_action

    def _should_execute_action(self, verdict: str, action_type: str) -> str:
        """Determine if an action should be executed based on verdict and action type."""
        # Actions that should execute regardless of verdict
        always_execute = ["alert", "monitor", "investigate"]
        
        # Actions that should execute only on confirmed verdict
        confirmed_only = ["proceed"]
        
        # Actions that should execute only on contradicted verdict
        contradicted_only = ["halt", "hedge"]
        
        if action_type in always_execute:
            return "Yes"
        elif action_type in confirmed_only:
            return "Yes" if verdict == "confirmed" else "No"
        elif action_type in contradicted_only:
            return "Yes" if verdict == "contradicted" else "No"
        
        # Default: execute for confirmed or partially confirmed
        return "Yes" if verdict in ["confirmed", "partially_confirmed"] else "No"

    def _fallback_actions(self, verdict: str, intent: dict) -> list[dict]:
        """Generate fallback actions if Gemini parse fails."""
        sector = intent.get("sector", "sector")
        if verdict == "contradicted":
            return [
                {"name": f"Alert: {sector} risk detected", "type": "alert",
                 "description": "Send alert about contradicted claim", "urgency": "high",
                 "constraint": {"type": "urgency", "value": "immediate"}, "depends_on": None},
                {"name": f"Halt {intent.get('action_suggested', 'action')}", "type": "halt",
                 "description": "Stop planned action due to contradicting evidence", "urgency": "high",
                 "constraint": {"type": "time_window", "value": "24h"}, "depends_on": 0},
                {"name": f"Investigate {sector} further", "type": "investigate",
                 "description": "Deep dive into contradicting data sources", "urgency": "medium",
                 "constraint": {"type": "time_window", "value": "48h"}, "depends_on": 1},
                {"name": f"Monitor {sector} daily", "type": "monitor",
                 "description": "Set up monitoring for sector changes", "urgency": "low",
                 "constraint": {"type": "time_window", "value": "7d"}, "depends_on": 2},
            ]
        else:
            return [
                {"name": f"Alert: {sector} opportunity confirmed", "type": "alert",
                 "description": "Notify team of confirmed opportunity", "urgency": "medium",
                 "constraint": {"type": "urgency", "value": "today"}, "depends_on": None},
                {"name": f"Proceed with {intent.get('action_suggested', 'plan')}", "type": "proceed",
                 "description": "Execute the suggested action with caution", "urgency": "medium",
                 "constraint": {"type": "budget", "value": 50000, "limit": 100000}, "depends_on": 0},
                {"name": f"Hedge {sector} exposure", "type": "hedge",
                 "description": "Set up protective positions", "urgency": "medium",
                 "constraint": {"type": "budget", "value": 10000, "limit": 25000}, "depends_on": 1},
                {"name": f"Monitor {sector} weekly", "type": "monitor",
                 "description": "Track sector metrics for changes", "urgency": "low",
                 "constraint": {"type": "time_window", "value": "7d"}, "depends_on": 2},
            ]
