"""Quick Brevo diagnostic — checks senders and fires a direct test email."""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY    = os.environ.get("BREVO_API_KEY", "")
FROM_EMAIL = os.environ.get("BREVO_FROM_EMAIL", "")
TO_EMAIL   = os.environ.get("TEST_EMAIL", "")

base_headers = {"api-key": API_KEY, "Accept": "application/json"}

# 1. Check account credits remaining
print("=== Account / Quota ===")
r = requests.get("https://api.brevo.com/v3/account", headers=base_headers, timeout=10)
acc = r.json()
for p in acc.get("plan", []):
    print(f"  type={p['type']}  credits={p['credits']}  ({p['creditsType']})")
print()

# 2. Check registered senders
print("=== Senders ===")
r2 = requests.get("https://api.brevo.com/v3/senders", headers=base_headers, timeout=10)
senders_data = r2.json()
for s in senders_data.get("senders", []):
    print(f"  email={s['email']}  active={s.get('active')}  id={s.get('id')}")
print()

# 3. Fire a direct test email RIGHT NOW
print(f"=== Sending test email to {TO_EMAIL} ===")
payload = {
    "sender": {"email": FROM_EMAIL},
    "to":     [{"email": TO_EMAIL}],
    "subject": "LaunchMind Brevo Diagnostic Test",
    "htmlContent": (
        "<html><body>"
        "<h2>LaunchMind Diagnostic</h2>"
        "<p>This is a direct Brevo test. If you see this, the API is working.</p>"
        "</body></html>"
    ),
}
send_headers = {
    "api-key":      API_KEY,
    "Content-Type": "application/json",
    "Accept":       "application/json",
}
r3 = requests.post(
    "https://api.brevo.com/v3/smtp/email",
    json=payload,
    headers=send_headers,
    timeout=15,
)
print(f"  HTTP status : {r3.status_code}")
print(f"  Response    : {r3.text}")

if r3.status_code == 201:
    print("\n  API accepted the email (201). Check spam folder if not in inbox.")
elif r3.status_code == 400:
    print("\n  400 Bad Request — sender may not be verified in Brevo.")
elif r3.status_code == 401:
    print("\n  401 Unauthorized — API key invalid or revoked.")
elif r3.status_code == 429:
    print("\n  429 Rate Limited — daily send limit hit.")
else:
    print(f"\n  Unexpected status {r3.status_code}")

# 4. Check email activity logs (last 10 events)
print("\n=== Recent Email Events (last 5) ===")
r4 = requests.get(
    "https://api.brevo.com/v3/smtp/statistics/events",
    headers=base_headers,
    params={"limit": 5, "sort": "desc"},
    timeout=10,
)
events_data = r4.json()
events = events_data.get("events", [])
if not events:
    print("  No events returned (may need Transactional Email enabled on account).")
for ev in events:
    print(f"  [{ev.get('date')}] to={ev.get('to')}  event={ev.get('event')}  subject={ev.get('subject', '')[:40]}")
