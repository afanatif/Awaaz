# db.py
#
# Awaz — SQLite persistence layer for execution state.
# Tables: pipeline_runs, transactions, hold_records

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "awaz.db"

_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
    return _conn


def init_db() -> None:
    """Create tables if they don't exist."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            id               TEXT PRIMARY KEY,
            input_type       TEXT NOT NULL,
            input_summary    TEXT,
            started_at       TEXT NOT NULL,
            completed_at     TEXT,
            total_latency_ms REAL,
            verdict          TEXT,
            status           TEXT DEFAULT 'running'
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id              TEXT PRIMARY KEY,
            pipeline_run_id TEXT NOT NULL,
            action_type     TEXT NOT NULL,
            action_name     TEXT,
            before_state    TEXT,
            after_state     TEXT,
            timestamp       TEXT NOT NULL,
            success         INTEGER DEFAULT 1,
            FOREIGN KEY (pipeline_run_id) REFERENCES pipeline_runs(id)
        );

        CREATE TABLE IF NOT EXISTS hold_records (
            id              TEXT PRIMARY KEY,
            pipeline_run_id TEXT NOT NULL,
            action_name     TEXT,
            reason          TEXT,
            hold_until      TEXT,
            timestamp       TEXT NOT NULL,
            FOREIGN KEY (pipeline_run_id) REFERENCES pipeline_runs(id)
        );
    """)
    conn.commit()


def create_pipeline_run(input_type: str, input_summary: str) -> str:
    """Insert a new pipeline run and return its ID."""
    run_id = str(uuid.uuid4())
    conn = _get_conn()
    conn.execute(
        "INSERT INTO pipeline_runs (id, input_type, input_summary, started_at) VALUES (?, ?, ?, ?)",
        (run_id, input_type, input_summary, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    return run_id


def complete_pipeline_run(run_id: str, verdict: str, total_latency_ms: float) -> None:
    """Mark a pipeline run as complete."""
    conn = _get_conn()
    conn.execute(
        "UPDATE pipeline_runs SET completed_at=?, total_latency_ms=?, verdict=?, status='completed' WHERE id=?",
        (datetime.now(timezone.utc).isoformat(), total_latency_ms, verdict, run_id),
    )
    conn.commit()


def write_transaction(
    pipeline_run_id: str,
    action_type: str,
    action_name: str,
    before_state: dict,
    after_state: dict,
    success: bool = True,
) -> str:
    """Write a transaction record and return its ID."""
    txn_id = str(uuid.uuid4())
    conn = _get_conn()
    conn.execute(
        """INSERT INTO transactions
           (id, pipeline_run_id, action_type, action_name, before_state, after_state, timestamp, success)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            txn_id,
            pipeline_run_id,
            action_type,
            action_name,
            json.dumps(before_state),
            json.dumps(after_state),
            datetime.now(timezone.utc).isoformat(),
            1 if success else 0,
        ),
    )
    conn.commit()
    return txn_id


def write_hold_record(
    pipeline_run_id: str,
    action_name: str,
    reason: str,
    hold_until: str | None = None,
) -> str:
    """Write a hold record and return its ID."""
    hold_id = str(uuid.uuid4())
    conn = _get_conn()
    conn.execute(
        "INSERT INTO hold_records (id, pipeline_run_id, action_name, reason, hold_until, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
        (
            hold_id,
            pipeline_run_id,
            action_name,
            reason,
            hold_until or "",
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    return hold_id


def get_portfolio_state(pipeline_run_id: str | None = None) -> dict:
    """Get current simulated portfolio state from latest transactions."""
    conn = _get_conn()
    if pipeline_run_id:
        rows = conn.execute(
            "SELECT * FROM transactions WHERE pipeline_run_id=? ORDER BY timestamp",
            (pipeline_run_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM transactions ORDER BY timestamp DESC LIMIT 10"
        ).fetchall()

    transactions = []
    for r in rows:
        transactions.append({
            "id": r["id"],
            "action_type": r["action_type"],
            "action_name": r["action_name"],
            "before_state": json.loads(r["before_state"]) if r["before_state"] else {},
            "after_state": json.loads(r["after_state"]) if r["after_state"] else {},
            "timestamp": r["timestamp"],
            "success": bool(r["success"]),
        })
    return {"transactions": transactions}
