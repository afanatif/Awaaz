# awaz_logger.py
#
# Awaz — Structured JSON logging for the entire pipeline.
# Every log entry is JSON with: timestamp, agent_name, event_type,
# input_summary, output_summary, duration_ms, error.
# Writes simultaneously to console and rotating file (awaz.log).

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Any

# ---------------------------------------------------------------------------
# ANSI colors for console output (agent-based color coding)
# ---------------------------------------------------------------------------

AGENT_COLORS = {
    "ingestion":  "\033[95m",   # purple
    "analyst":    "\033[96m",   # teal/cyan
    "strategist": "\033[94m",   # blue
    "executor":   "\033[92m",   # green
    "monitor":    "\033[93m",   # amber/yellow
    "system":     "\033[97m",   # white
}
COLOR_RED   = "\033[91m"
COLOR_RESET = "\033[0m"

# ---------------------------------------------------------------------------
# Global log store for real-time streaming to frontend
# ---------------------------------------------------------------------------

_log_entries: list[dict] = []
_log_callbacks: list = []   # callable(entry) — called on every new log


def register_log_callback(cb) -> None:
    """Register a callback that fires on every new log entry (for WebSocket)."""
    _log_callbacks.append(cb)


def get_log_entries(start: int = 0) -> list[dict]:
    """Return log entries from index `start` onward."""
    return _log_entries[start:]


# ---------------------------------------------------------------------------
# JSON formatter for file output
# ---------------------------------------------------------------------------

class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = getattr(record, "_awaz_entry", None)
        if entry:
            return json.dumps(entry, ensure_ascii=False)
        # Fallback for non-Awaz log records
        return json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_name": "system",
            "event_type": "generic",
            "message": record.getMessage(),
        }, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Console formatter with color coding
# ---------------------------------------------------------------------------

class _ConsoleFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = getattr(record, "_awaz_entry", None)
        if not entry:
            return record.getMessage()

        agent = entry.get("agent_name", "system")
        event = entry.get("event_type", "")
        error = entry.get("error")

        # Red for failures regardless of agent
        if error or "fail" in event.lower():
            color = COLOR_RED
        else:
            color = AGENT_COLORS.get(agent, "\033[97m")

        ts = entry.get("timestamp", "")[-12:]  # just HH:MM:SS.sss
        duration = entry.get("duration_ms")
        dur_str = f" ({duration}ms)" if duration is not None else ""

        summary = entry.get("output_summary", entry.get("input_summary", ""))
        if isinstance(summary, dict):
            summary = json.dumps(summary, ensure_ascii=False)[:120]
        elif isinstance(summary, str) and len(summary) > 120:
            summary = summary[:117] + "..."

        line = f"{color}[{ts}] [{agent.upper():>11}] {event}{dur_str}{COLOR_RESET}"
        if summary:
            line += f"\n{'':>16}{summary}"
        if error:
            line += f"\n{'':>16}{COLOR_RED}ERROR: {error}{COLOR_RESET}"

        return line


# ---------------------------------------------------------------------------
# Logger setup (called once at startup)
# ---------------------------------------------------------------------------

_logger: logging.Logger | None = None


def setup_logger(log_file: str = "awaz.log") -> logging.Logger:
    """Configure and return the Awaz structured logger."""
    global _logger
    if _logger is not None:
        return _logger

    logger = logging.getLogger("awaz")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    # File handler — rotating, JSON lines
    fh = RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(_JsonFormatter())
    logger.addHandler(fh)

    # Console handler — colored, human-readable
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(_ConsoleFormatter())
    logger.addHandler(ch)

    _logger = logger
    return logger


# ---------------------------------------------------------------------------
# Public API — awaz_log()
# ---------------------------------------------------------------------------

def awaz_log(
    agent: str,
    event_type: str,
    *,
    input_summary: Any = None,
    output_summary: Any = None,
    duration_ms: int | float | None = None,
    error: str | None = None,
    **extra: Any,
) -> dict:
    """
    Emit a structured log entry.

    Parameters
    ----------
    agent       : Agent name (ingestion, analyst, strategist, executor, monitor, system)
    event_type  : One of the ~25 canonical event types
    input_summary  : Brief description of input
    output_summary : Brief description of output / result
    duration_ms    : Elapsed time in milliseconds
    error          : Error message if something failed
    **extra        : Any additional key-value pairs to include

    Returns
    -------
    dict  The log entry that was written.
    """
    logger = _logger or setup_logger()

    entry: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent_name": agent,
        "event_type": event_type,
    }

    if input_summary is not None:
        entry["input_summary"] = input_summary
    if output_summary is not None:
        entry["output_summary"] = output_summary
    if duration_ms is not None:
        entry["duration_ms"] = round(duration_ms, 1)
    if error is not None:
        entry["error"] = error

    # Merge extra fields
    entry.update(extra)

    # Create log record with our custom entry attached
    record = logging.LogRecord(
        name="awaz",
        level=logging.INFO if not error else logging.ERROR,
        pathname="",
        lineno=0,
        msg="",
        args=(),
        exc_info=None,
    )
    record._awaz_entry = entry  # type: ignore[attr-defined]

    logger.handle(record)

    # Store for frontend streaming
    _log_entries.append(entry)

    # Fire callbacks for real-time WebSocket push
    for cb in _log_callbacks:
        try:
            cb(entry)
        except Exception as e:
            print(f"Callback error: {e}")

    return entry


# ---------------------------------------------------------------------------
# Timer context manager
# ---------------------------------------------------------------------------

class LogTimer:
    """Context manager that measures elapsed time in ms."""

    def __init__(self):
        self.start_time: float = 0
        self.elapsed_ms: float = 0

    def __enter__(self) -> "LogTimer":
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *_: Any) -> None:
        self.elapsed_ms = (time.perf_counter() - self.start_time) * 1000
