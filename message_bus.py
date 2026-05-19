# message_bus.py
#
# Awaz — Shared in-memory message bus with full communication logging.

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Shared in-memory message bus  (agent_name → list of pending messages)
# ---------------------------------------------------------------------------

message_bus: dict[str, list] = {
    "ingestion":  [],
    "analyst":    [],
    "strategist": [],
    "executor":   [],
    "monitor":    [],
}

# Immutable audit log — every message ever sent, never cleared.
full_message_log: list[dict] = []

# ---------------------------------------------------------------------------
# Internal logger
# ---------------------------------------------------------------------------

def _log_send(message: dict) -> None:
    """Print a structured, human-readable log entry for a sent message."""
    sender   = message["from_agent"].upper()
    receiver = message["to_agent"].upper()
    mtype    = message["message_type"]
    mid      = message["message_id"][:8]
    ts       = message["timestamp"]
    parent   = message.get("parent_message_id")
    size     = message.get("payload_size_bytes", "?")

    # Build a compact payload preview (strip large blobs)
    payload  = message.get("payload", {})
    keys     = list(payload.keys()) if isinstance(payload, dict) else []
    preview  = ", ".join(f"{k}=..." for k in keys) if keys else str(payload)[:60]

    line = (
        f"\n  [MSG BUS] "
        f"{sender} --> {receiver} | type={mtype} | id={mid} | {size}B | {ts}\n"
        f"            payload keys: [{preview}]"
    )
    if parent:
        line += f"\n            reply-to: {parent[:8]}"

    print(line)

    # Also log to Awaz structured logger if available
    try:
        from awaz_logger import awaz_log
        awaz_log(
            agent="system",
            event_type="message_sent",
            input_summary=f"{sender} -> {receiver}",
            output_summary=f"type={mtype}, keys=[{preview}]",
            sender=message["from_agent"],
            receiver=message["to_agent"],
            message_id=message["message_id"],
            payload_size_bytes=size,
        )
    except Exception:
        pass


def _log_receive(agent_name: str, count: int) -> None:
    """Print a log entry when an agent drains its inbox."""
    ts = datetime.now(timezone.utc).isoformat()
    if count:
        print(
            f"\n  [MSG BUS] {agent_name.upper()} collected {count} "
            f"message(s) from inbox | {ts}"
        )
    else:
        print(f"\n  [MSG BUS] {agent_name.upper()} inbox empty | {ts}")

    try:
        from awaz_logger import awaz_log
        awaz_log(
            agent="system",
            event_type="message_received",
            input_summary=f"{agent_name} inbox",
            output_summary=f"{count} message(s)",
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def send_message(
    from_agent: str,
    to_agent: str,
    message_type: str,
    payload: dict,
    parent_id: str | None = None,
) -> str:
    """
    Create a structured message, route it to the recipient's inbox,
    append it to the immutable audit log, and print a log entry.

    Parameters
    ----------
    from_agent    : name of the sending agent   (e.g. "ingestion")
    to_agent      : name of the target agent    (e.g. "analyst")
    message_type  : "task" | "result" | "revision_request" | "confirmation"
    payload       : dict with the actual content
    parent_id     : optional message_id of the message being replied to

    Returns
    -------
    str  The newly generated message_id.
    """
    message_id = str(uuid.uuid4())

    # Calculate payload size
    try:
        payload_size = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    except Exception:
        payload_size = 0

    message = {
        "message_id":        message_id,
        "from_agent":        from_agent,
        "to_agent":          to_agent,
        "message_type":      message_type,
        "payload":           payload,
        "payload_size_bytes": payload_size,
        "timestamp":         datetime.now(timezone.utc).isoformat(),
        "parent_message_id": parent_id,
    }

    # Route to recipient's inbox (create inbox if new agent name)
    if to_agent not in message_bus:
        message_bus[to_agent] = []
    message_bus[to_agent].append(message)

    # Append to the immutable audit log
    full_message_log.append(message)

    # Human-readable log
    _log_send(message)

    return message_id


def receive_messages(agent_name: str) -> list[dict]:
    """
    Return all pending messages for *agent_name* and clear that inbox.

    Parameters
    ----------
    agent_name : the agent whose inbox we are draining

    Returns
    -------
    list[dict]  The messages that were waiting (may be empty).
    """
    if agent_name not in message_bus:
        _log_receive(agent_name, 0)
        return []

    messages = list(message_bus[agent_name])
    message_bus[agent_name].clear()

    _log_receive(agent_name, len(messages))
    return messages
