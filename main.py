# main.py
# Awaz — CLI Orchestrator

import argparse
import json
import os
import sys
import time

from dotenv import load_dotenv

import db
import message_bus
from awaz_logger import awaz_log, setup_logger
from mock_server import start_mock_server

load_dotenv()


def print_message_log(full_message_log: list) -> None:
    print("\n" + "=" * 70)
    print("  AWAZ PIPELINE COMMUNICATION LOG")
    print("=" * 70)
    if not full_message_log:
        print("  (no messages recorded)")
    else:
        for i, msg in enumerate(full_message_log, start=1):
            print(f"\n[{i}] {msg['from_agent'].upper()} → {msg['to_agent'].upper()} "
                  f"| type={msg['message_type']} | id={msg['message_id'][:8]}...")
            print(f"     timestamp : {msg['timestamp']}")
            if msg.get("parent_message_id"):
                print(f"     reply-to  : {msg['parent_message_id'][:8]}...")
            try:
                payload_str = json.dumps(msg["payload"], indent=6)
                if len(payload_str) > 600:
                    payload_str = payload_str[:597] + "..."
                print(f"     payload   :\n{payload_str}")
            except Exception:
                pass
    print("\n" + "=" * 70 + "\n")


def save_message_log_txt(full_message_log: list, path: str = "message_log.txt") -> None:
    lines = ["=" * 90, "Awaz - Complete Agent Communication Log", "=" * 90, ""]
    for i, msg in enumerate(full_message_log, start=1):
        lines.append("-" * 90)
        lines.append(f"[{i}] {msg.get('timestamp')}")
        lines.append(f"FLOW       : {msg.get('from_agent', '').upper()} -> {msg.get('to_agent', '').upper()}")
        lines.append(f"TYPE       : {msg.get('message_type')}")
        lines.append(f"PAYLOAD    :")
        lines.append(json.dumps(msg.get("payload", {}), indent=2, ensure_ascii=True))
        lines.append("")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except Exception:
        pass


def run_pipeline(input_type: str, input_data: str):
    setup_logger()
    db.init_db()

    # Start mock server for failure simulation
    start_mock_server(5001)

    awaz_log("system", "startup", input_summary=f"type={input_type}",
             output_summary="Starting pipeline")

    run_id = db.create_pipeline_run(input_type, input_data[:100])
    start_time = time.perf_counter()

    # 1. Ingestion
    from agents.ingestion_agent import IngestionAgent
    IngestionAgent().run(input_type, input_data)

    # 2. Analyst
    from agents.analyst_agent import AnalystAgent
    AnalystAgent().run()

    # 3. Strategist
    from agents.strategist_agent import StrategistAgent
    StrategistAgent().run()

    # 4. Executor
    from agents.executor_agent import ExecutorAgent
    ExecutorAgent().run(pipeline_run_id=run_id)

    # 5. Monitor
    from agents.monitor_agent import MonitorAgent
    MonitorAgent().run()

    # Get final result message sent to 'system'
    system_msgs = message_bus.receive_messages("system")
    outcome_file = ""
    verdict = "unknown"
    if system_msgs:
        payload = system_msgs[0].get("payload", {})
        outcome_file = payload.get("outcome_file", "")
        verdict = payload.get("outcome", {}).get("verdict", "unknown")

    total_latency_ms = (time.perf_counter() - start_time) * 1000
    db.complete_pipeline_run(run_id, verdict, total_latency_ms)

    awaz_log("system", "pipeline_completed",
             output_summary=f"verdict={verdict}",
             duration_ms=total_latency_ms)

    print_message_log(message_bus.full_message_log)

    try:
        with open("message_log.json", "w", encoding="utf-8") as f:
            json.dump(message_bus.full_message_log, f, indent=4)
        save_message_log_txt(message_bus.full_message_log)
    except Exception:
        pass

    if outcome_file:
        print(f"\n🎉 Pipeline complete! Outcome saved to: {outcome_file}")


def main():
    parser = argparse.ArgumentParser(description="Awaz Voice & Text Intelligence Pipeline")
    parser.add_argument("--text", type=str, help="Run with text input")
    parser.add_argument("--voice", type=str, help="Run with voice input (path to audio file)")
    args = parser.parse_args()

    if not os.environ.get("GEMINI_API_KEY"):
        print("❌ GEMINI_API_KEY is not set in .env")
        sys.exit(1)

    if args.text:
        run_pipeline("text", args.text)
    elif args.voice:
        run_pipeline("voice", args.voice)
    else:
        print("Usage: python main.py --text \"business claim\" OR python main.py --voice path/to/audio.wav")
        # Run demo
        print("Running text demo...")
        run_pipeline("text", "Boss ne kaha hai ke oil sector mein invest karo, prices barh rahe hain aur OPEC ne production cut ki hai")


if __name__ == "__main__":
    main()
