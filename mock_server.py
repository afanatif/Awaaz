# mock_server.py
# Awaz — Mock internal API that deliberately fails on first call.
# Used by executor_agent to demonstrate failure recovery.

from __future__ import annotations
import threading
import time
from flask import Flask, jsonify

app = Flask(__name__)
_call_count = 0
_lock = threading.Lock()


@app.route("/api/internal/execute", methods=["POST"])
def execute():
    global _call_count
    with _lock:
        _call_count += 1
        current = _call_count

    if current == 1:
        return jsonify({"error": "Service temporarily unavailable", "code": 503}), 503
    return jsonify({"status": "success", "message": "Action executed successfully",
                    "execution_id": f"exec-{current}"}), 200


@app.route("/api/internal/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"}), 200


@app.route("/api/internal/reset", methods=["POST"])
def reset():
    global _call_count
    with _lock:
        _call_count = 0
    return jsonify({"status": "reset"}), 200


def start_mock_server(port: int = 5001) -> threading.Thread:
    """Start the mock server in a background daemon thread."""
    def _run():
        app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)

    t = threading.Thread(target=_run, daemon=True, name="mock-server")
    t.start()
    time.sleep(0.5)  # Give server time to start
    return t


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)
