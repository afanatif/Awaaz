# agents/ingestion_agent.py
# Awaz Agent 1 — Ingestion & Transcription (repurposed from CEO agent)
# Handles: voice transcription (Whisper), text input, language detection,
# intent extraction (Gemini), parallel source fetching.

from __future__ import annotations
import json, os, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from google import genai
from message_bus import send_message, receive_messages
from awaz_logger import awaz_log, LogTimer
from sources.news_fetcher import fetch_news
from sources.market_fetcher import fetch_market_data
from sources.reddit_fetcher import fetch_reddit_sentiment
from sources.regulatory_fetcher import fetch_regulatory_context
from sources.business_recorder_scraper import fetch_business_recorder_news
from sources.psx_scraper import fetch_psx_snapshot
from sources.dawn_business_scraper import fetch_dawn_business_news
from sources.profit_pakistan_scraper import fetch_profit_pakistan_news


class IngestionAgent:
    """
    Agent 1: Receives raw input (audio or text), transcribes if needed,
    extracts structured intent, fetches all 4 data sources in parallel,
    and sends everything to the Analyst agent.
    """

    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise EnvironmentError("[INGESTION] GEMINI_API_KEY not set.")
        self.client = genai.Client(api_key=api_key)
        self.agent_name = "ingestion"
        self.whisper_model_name = os.environ.get("WHISPER_MODEL", "base")
        self._whisper_model = None

    def _call_gemini(self, system_prompt: str, user_prompt: str, retries: int = 1) -> str:
        for attempt in range(retries + 1):
            try:
                response = self.client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=user_prompt,
                    config=genai.types.GenerateContentConfig(system_instruction=system_prompt),
                )
                return response.text
            except Exception as exc:
                if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc) or "503" in str(exc):
                    return self._call_hf(system_prompt, user_prompt)
                if attempt < retries:
                    time.sleep(2)
                else:
                    raise

    def _call_hf(self, system_prompt: str, user_prompt: str) -> str:
        from huggingface_hub import InferenceClient
        try:
            client = InferenceClient(api_key=os.environ.get("HF_API_KEY", ""))
            resp = client.chat_completion(
                model="meta-llama/Llama-3.3-70B-Instruct",
                messages=[{"role": "system", "content": system_prompt},
                          {"role": "user", "content": user_prompt}],
                max_tokens=4000)
            return resp.choices[0].message.content or ""
        except Exception as exc:
            awaz_log(self.agent_name, "llm_fallback_failed", error=str(exc))
            return ""

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def run(self, input_type: str, input_data: str) -> None:
        """
        Main entry point.
        input_type: 'voice' or 'text'
        input_data: file path (voice) or raw text string (text)
        """
        awaz_log("system", "input_received", input_summary=f"type={input_type}",
                 output_summary=input_data[:100] if input_type == "text" else input_data)

        with LogTimer() as total_timer:
            # Step 1: Get transcription / clean text
            if input_type == "voice":
                text = self._transcribe(input_data)
            else:
                text = input_data

            # Step 2: Language detection & translation
            text = self._handle_language(text)

            # Step 3: Extract structured intent
            intent = self._extract_intent(text)

            # Step 4: Extract keywords for source queries
            keywords = self._extract_keywords(text, intent)

            # Step 5: Parallel source fetching
            source_data = self._fetch_all_sources(keywords, intent.get("sector", "general"))

        awaz_log(self.agent_name, "ingestion_complete",
                 output_summary=f"intent={intent.get('claim','')[:80]}",
                 duration_ms=total_timer.elapsed_ms)

        # Send to Analyst via message bus
        send_message(
            from_agent=self.agent_name, to_agent="analyst", message_type="task",
            payload={
                "original_input": input_data if input_type == "text" else f"[audio:{input_data}]",
                "input_type": input_type,
                "transcription": text,
                "intent": intent,
                "keywords": keywords,
                "news_data": source_data.get("news", {}),
                "market_data": source_data.get("market", {}),
                "reddit_data": source_data.get("reddit", {}),
                "regulatory_data": source_data.get("regulatory", {}),
                "business_recorder_data": source_data.get("business_recorder", {}),
                "psx_data": source_data.get("psx", {}),
                "dawn_business_data": source_data.get("dawn_business", {}),
                "profit_pakistan_data": source_data.get("profit_pakistan", {}),
                "total_ingestion_ms": round(total_timer.elapsed_ms, 1),
            })

    # ------------------------------------------------------------------
    # Whisper transcription
    # ------------------------------------------------------------------
    def _transcribe(self, audio_path: str) -> str:
        awaz_log(self.agent_name, "whisper_transcription_started",
                 input_summary=audio_path, output_summary=f"model={self.whisper_model_name}")

        with LogTimer() as t:
            try:
                import whisper
                if self._whisper_model is None:
                    self._whisper_model = whisper.load_model(self.whisper_model_name)
                result = self._whisper_model.transcribe(audio_path)
                text = result.get("text", "").strip()
                duration = result.get("segments", [{}])
                audio_duration = duration[-1].get("end", 0) if duration else 0
            except Exception as exc:
                awaz_log(self.agent_name, "whisper_transcription_failed",
                         error=str(exc))
                return f"[Transcription failed: {exc}]"

        file_size = os.path.getsize(audio_path) if os.path.exists(audio_path) else 0
        awaz_log(self.agent_name, "whisper_transcription_completed",
                 input_summary=f"file_size={file_size}B, audio_duration={audio_duration:.1f}s",
                 output_summary=text[:200], duration_ms=t.elapsed_ms,
                 model=self.whisper_model_name, audio_duration_seconds=round(audio_duration, 1))
        return text

    # ------------------------------------------------------------------
    # Language handling
    # ------------------------------------------------------------------
    def _handle_language(self, text: str) -> str:
        sys_prompt = (
            "You are a language detector. Determine if the text is in English, Urdu, or Roman Urdu. "
            "If it is NOT in English, translate it to English. "
            "Return ONLY valid JSON: {\"language\": \"english|urdu|roman_urdu\", \"translated\": \"english text\"}"
        )
        with LogTimer() as t:
            raw = self._call_gemini(sys_prompt, f"Detect language and translate if needed:\n{text}")

        try:
            result = json.loads(raw.strip().strip("```json").strip("```"))
        except json.JSONDecodeError:
            if any(c in text for c in "آابپتٹجچحخدڈذرڑزژسشصضطظعغفقکگلمنوہیے"):
                result = {"language": "urdu", "translated": text}
            else:
                result = {"language": "english", "translated": text}

        lang = result.get("language", "english")
        translated = result.get("translated", text)

        if lang != "english":
            awaz_log(self.agent_name, "language_translation",
                     input_summary=f"lang={lang}: {text[:100]}",
                     output_summary=f"translated: {translated[:100]}",
                     duration_ms=t.elapsed_ms)
            return translated
        return text

    # ------------------------------------------------------------------
    # Intent extraction
    # ------------------------------------------------------------------
    def _extract_intent(self, text: str) -> dict:
        sys_prompt = (
            "You are a business intent extraction engine. Extract structured intent from the text. "
            "Return ONLY valid JSON with NO markdown:\n"
            '{"claim": "the main assertion", "sector": "business sector", '
            '"action_suggested": "what the human wants to do", "confidence": 0.0 to 1.0}'
        )
        awaz_log(self.agent_name, "gemini_intent_extraction_started", input_summary=text[:100])
        with LogTimer() as t:
            raw = self._call_gemini(sys_prompt, f"Extract business intent:\n{text}")

        try:
            clean = raw.strip().strip("```json").strip("```").strip()
            intent = json.loads(clean)
        except json.JSONDecodeError:
            intent = {"claim": text, "sector": "general", "action_suggested": "investigate", "confidence": 0.5}

        awaz_log(self.agent_name, "gemini_intent_extraction_completed",
                 input_summary=text[:80], output_summary=json.dumps(intent)[:200],
                 duration_ms=t.elapsed_ms)
        return intent

    # ------------------------------------------------------------------
    # Keyword extraction
    # ------------------------------------------------------------------
    def _extract_keywords(self, text: str, intent: dict) -> list[str]:
        sys_prompt = (
            "Extract 3 to 5 search keywords from this business claim for querying news and market data. "
            "Return ONLY a JSON array of strings. No markdown."
        )
        raw = self._call_gemini(sys_prompt,
            f"Claim: {intent.get('claim', text)}\nSector: {intent.get('sector', '')}")
        try:
            clean = raw.strip().strip("```json").strip("```").strip()
            kws = json.loads(clean)
            if isinstance(kws, list):
                return [str(k) for k in kws[:5]]
        except Exception:
            pass
        # Fallback: use sector and words from claim
        words = intent.get("claim", text).split()[:4]
        sector = intent.get("sector", "")
        return list(set([sector] + words)) if sector else words

    # ------------------------------------------------------------------
    # Parallel source fetching
    # ------------------------------------------------------------------
    def _fetch_all_sources(self, keywords: list[str], sector: str) -> dict[str, Any]:
        awaz_log(self.agent_name, "parallel_fetch_started",
                 input_summary=f"keywords={keywords}, sector={sector}")

        results = {}
        with LogTimer() as t:
            with ThreadPoolExecutor(max_workers=8) as pool:
                futures = {
                    pool.submit(fetch_news, keywords): "news",
                    pool.submit(fetch_market_data, sector): "market",
                    pool.submit(fetch_reddit_sentiment, keywords): "reddit",
                    pool.submit(fetch_regulatory_context): "regulatory",
                    pool.submit(fetch_business_recorder_news): "business_recorder",
                    pool.submit(fetch_psx_snapshot): "psx",
                    pool.submit(fetch_dawn_business_news): "dawn_business",
                    pool.submit(fetch_profit_pakistan_news): "profit_pakistan",
                }
                for future in as_completed(futures):
                    name = futures[future]
                    try:
                        results[name] = future.result(timeout=30)
                    except Exception as exc:
                        awaz_log(self.agent_name, "source_fetch_failed",
                                 input_summary=name, error=str(exc))
                        results[name] = {"source": name, "error": str(exc)}

        awaz_log(self.agent_name, "parallel_fetch_completed",
                 output_summary=f"sources={list(results.keys())}",
                 duration_ms=t.elapsed_ms)
        return results
