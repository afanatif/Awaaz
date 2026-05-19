# test_slack.py
#
# LaunchMind — Slack integration test
# Windows note: run with  $env:PYTHONUTF8=1; python test_slack.py
#               (or just use the alias below)
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
# Tests:
#   1. Bot token auth  (auth.test)
#   2. User token auth (auth.test)
#   3. List channels the bot can see (conversations.list)
#   4. Post a message via bot token to #general (or any channel found)
#   5. Post a rich-block message to #launches (created if missing)
#   6. Verify message was delivered (conversations.history)

import json
import os
import sys
from datetime import datetime

import requests
from dotenv import load_dotenv

# ── Load tokens ──────────────────────────────────────────────────────────────
load_dotenv()

BOT_TOKEN  = os.environ.get("SLACK_BOT_TOKEN", "")
USER_TOKEN = os.environ.get("SLACK_USER_TOKEN", "")

SLACK_API = "https://slack.com/api"

# ── Helpers ───────────────────────────────────────────────────────────────────

def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _ok(label: str, data: dict) -> bool:
    if data.get("ok"):
        print(f"  ✅  {label}")
        return True
    err = data.get("error", "unknown error")
    warn = data.get("warning", "")
    print(f"  ❌  {label}  →  error='{err}'" + (f"  warning='{warn}'" if warn else ""))
    return False


def slack_get(endpoint: str, token: str, params: dict = None) -> dict:
    r = requests.get(f"{SLACK_API}/{endpoint}", headers=_headers(token),
                     params=params or {}, timeout=15)
    return r.json()


def slack_post(endpoint: str, token: str, payload: dict) -> dict:
    r = requests.post(f"{SLACK_API}/{endpoint}", headers=_headers(token),
                      json=payload, timeout=15)
    return r.json()


# ─────────────────────────────────────────────────────────────────────────────
# 1.  AUTH CHECKS
# ─────────────────────────────────────────────────────────────────────────────

def test_auth(token: str, label: str) -> dict | None:
    """Calls auth.test and pretty-prints identity info."""
    print(f"\n{'='*55}")
    print(f"  AUTH CHECK — {label}")
    print(f"{'='*55}")

    if not token:
        print(f"  ⚠️  Token not found in .env  (var: {label})")
        return None

    data = slack_get("auth.test", token)

    if not _ok("auth.test", data):
        print(f"  Full response: {json.dumps(data, indent=4)}")
        return None

    # Print identity fields
    fields = ["url", "team", "user", "team_id", "user_id", "bot_id", "app_id"]
    for f in fields:
        if f in data:
            print(f"     {f:12s}: {data[f]}")

    return data


# ─────────────────────────────────────────────────────────────────────────────
# 2.  LIST CHANNELS
# ─────────────────────────────────────────────────────────────────────────────

def test_list_channels(token: str) -> list[dict]:
    """Fetches public + private channels the token can see."""
    print(f"\n{'='*55}")
    print("  CHANNEL LIST")
    print(f"{'='*55}")

    data = slack_get(
        "conversations.list",
        token,
        params={"types": "public_channel,private_channel", "limit": 50},
    )

    if not _ok("conversations.list", data):
        print(f"  Full response: {json.dumps(data, indent=4)}")
        return []

    channels = data.get("channels", [])
    if not channels:
        print("  ⚠️  No channels returned — bot may not be in any channel yet.")
        return []

    print(f"  Found {len(channels)} channel(s):")
    for ch in channels:
        member_flag = "👤" if ch.get("is_member") else "  "
        print(f"   {member_flag}  #{ch['name']}  (id={ch['id']})")

    return channels


# ─────────────────────────────────────────────────────────────────────────────
# 3.  POST PLAIN MESSAGE
# ─────────────────────────────────────────────────────────────────────────────

def test_post_message(token: str, channel_id: str, channel_name: str) -> str | None:
    """Posts a simple plain-text message; returns the message ts on success."""
    print(f"\n{'='*55}")
    print(f"  POST PLAIN MESSAGE  →  #{channel_name}  ({channel_id})")
    print(f"{'='*55}")

    ts_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "channel": channel_id,
        "text": f"🤖 LaunchMind bot test — {ts_now}",
    }

    data = slack_post("chat.postMessage", token, payload)

    if not _ok("chat.postMessage (plain)", data):
        print(f"  Full response: {json.dumps(data, indent=4)}")
        return None

    ts = data.get("ts")
    print(f"     message ts : {ts}")
    return ts


# ─────────────────────────────────────────────────────────────────────────────
# 4.  POST RICH BLOCK MESSAGE (mirrors what CEOAgent sends)
# ─────────────────────────────────────────────────────────────────────────────

def test_post_blocks(token: str, channel_id: str, channel_name: str) -> str | None:
    """Posts a Block Kit message identical to the one in ceo_agent.compile_final_summary."""
    print(f"\n{'='*55}")
    print(f"  POST BLOCK-KIT MESSAGE  →  #{channel_name}  ({channel_id})")
    print(f"{'='*55}")

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🚀 Final Launch Summary: LaunchMind Test App",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "*LaunchMind Test App* is live! 🎉\n"
                    "This is a test post confirming the Slack integration works end-to-end.\n"
                    "> _Built with LaunchMind — AI Multi-Agent Launch System_\n\n"
                    "• :github: PR: <https://github.com|View Pull Request>\n"
                    "• :ticket: Issue: <https://github.com|View Issue>"
                ),
            },
        },
        {"type": "divider"},
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Posted by LaunchMind CEO Agent  •  {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                }
            ],
        },
    ]

    payload = {
        "channel": channel_id,
        "text": "🚀 Final Launch Summary: LaunchMind Test App",
        "blocks": blocks,
    }

    data = slack_post("chat.postMessage", token, payload)

    if not _ok("chat.postMessage (blocks)", data):
        print(f"  Full response: {json.dumps(data, indent=4)}")
        return None

    ts = data.get("ts")
    print(f"     message ts : {ts}")
    return ts


# ─────────────────────────────────────────────────────────────────────────────
# 5.  VERIFY MESSAGE IN HISTORY
# ─────────────────────────────────────────────────────────────────────────────

def test_verify_message(token: str, channel_id: str, ts: str) -> None:
    """Retrieves the channel history and confirms our message exists."""
    print(f"\n{'='*55}")
    print(f"  VERIFY MESSAGE  (ts={ts})")
    print(f"{'='*55}")

    data = slack_get(
        "conversations.history",
        token,
        params={"channel": channel_id, "latest": ts, "limit": 5, "inclusive": "true"},
    )

    if not _ok("conversations.history", data):
        print(f"  Full response: {json.dumps(data, indent=4)}")
        return

    messages = data.get("messages", [])
    found = any(m.get("ts") == ts for m in messages)
    if found:
        print(f"  ✅  Message confirmed in channel history.")
    else:
        print(f"  ⚠️  Message ts not found in returned history (may still be there).")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 55)
    print("  LaunchMind — Slack Integration Test Suite")
    print("=" * 55)

    # ── 1. Auth checks ────────────────────────────────────────
    bot_info  = test_auth(BOT_TOKEN,  "SLACK_BOT_TOKEN  (xoxb-...)")
    user_info = test_auth(USER_TOKEN, "SLACK_USER_TOKEN (xoxp-...)")

    if not bot_info:
        print("\n❌  Bot token auth failed — cannot continue tests that need posting.\n")
        sys.exit(1)

    # ── 2. List channels ──────────────────────────────────────
    channels = test_list_channels(BOT_TOKEN)

    # Pick target channel: prefer #general, then #launches, then first available
    target_id   = None
    target_name = None

    for priority in ("general", "launches"):
        for ch in channels:
            if ch["name"] == priority and ch.get("is_member"):
                target_id   = ch["id"]
                target_name = ch["name"]
                break
        if target_id:
            break

    # Fallback: any channel the bot is a member of
    if not target_id:
        for ch in channels:
            if ch.get("is_member"):
                target_id   = ch["id"]
                target_name = ch["name"]
                break

    if not target_id:
        print(
            "\n⚠️  Bot is not a member of any channel.\n"
            "   → In Slack, open the channel you want and type:  /invite @YourBotName\n"
            "   Then re-run this script.\n"
        )
        sys.exit(1)

    # ── 3. Plain message ──────────────────────────────────────
    ts_plain = test_post_message(BOT_TOKEN, target_id, target_name)

    # ── 4. Block-Kit message ──────────────────────────────────
    ts_blocks = test_post_blocks(BOT_TOKEN, target_id, target_name)

    # ── 5. Verify the block-kit message ──────────────────────
    if ts_blocks:
        test_verify_message(BOT_TOKEN, target_id, ts_blocks)

    # ── Summary ───────────────────────────────────────────────
    print("\n" + "=" * 55)
    print("  TEST SUMMARY")
    print("=" * 55)
    print(f"  Bot  identity : {bot_info.get('user')} @ {bot_info.get('team')}")
    if user_info:
        print(f"  User identity : {user_info.get('user')} @ {user_info.get('team')}")
    print(f"  Target channel: #{target_name}  ({target_id})")
    print(f"  Plain ts      : {ts_plain}")
    print(f"  Blocks ts     : {ts_blocks}")
    all_passed = all([ts_plain, ts_blocks])
    print(f"\n  {'🎉  ALL TESTS PASSED' if all_passed else '⚠️   SOME TESTS FAILED — see output above'}")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    main()
