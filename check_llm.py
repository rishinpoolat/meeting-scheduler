"""Manual end-to-end check of the llm package against the real Anthropic API.

Run this with a real ANTHROPIC_API_KEY in .env (see config.py). Exercises
classify_email() against one hand-written email per intent, and each of the
four draft_* reply-drafting functions against fixture data. Prints results
for human review — no assertions, no Gmail/Calendar API calls (llm/ is pure).
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from gcalendar.events import Hold
from gcalendar.slots import TimeSlot
from gmail.read import Message
from llm.classify import classify_email
from llm.client import get_client
from llm.draft import (
    draft_booking_confirmation,
    draft_slot_confirmed,
    draft_slot_offer,
    draft_time_unavailable,
)

TZ = ZoneInfo("America/New_York")
NOW = datetime(2026, 7, 7, 9, 0, tzinfo=TZ)  # a Tuesday

MESSAGE = Message(
    id="check-llm-manual-test",
    thread_id="check-llm-manual-test-thread",
    subject="Meeting request",
    from_address="Jordan Smith <jordan@example.com>",
    message_id_header="<check-llm-manual-test@example.com>",
    references_header="",
    snippet="",
)

CANDIDATE_HOLDS = [
    Hold(
        id="hold-1",
        thread_id=MESSAGE.thread_id,
        start=NOW + timedelta(days=1, hours=1),
        end=NOW + timedelta(days=1, hours=1, minutes=30),
        created=NOW,
    ),
    Hold(
        id="hold-2",
        thread_id=MESSAGE.thread_id,
        start=NOW + timedelta(days=2, hours=5),
        end=NOW + timedelta(days=2, hours=5, minutes=30),
        created=NOW,
    ),
]

EMAILS = {
    "propose_time": "Hi, could we meet this Thursday at 2pm? Let me know if that works.",
    "ask_availability": "Hi, I'd love to chat sometime next week. What does your availability look like?",
    "irrelevant": "50% off all products this week only! Click here to unsubscribe.",
    "accept_slot": "Option 2 works great for me, see you then!",
}


def main() -> None:
    client = get_client()

    print("--- classify_email ---")
    for label, body in EMAILS.items():
        candidate_holds = CANDIDATE_HOLDS if label == "accept_slot" else []
        result = classify_email(client, MESSAGE, body, NOW, candidate_holds)
        print(f"\n[{label}] body={body!r}")
        print(f"  -> {result}")

    print("\n--- draft_* ---")
    start, end = (
        NOW + timedelta(days=1, hours=1),
        NOW + timedelta(days=1, hours=1, minutes=30),
    )
    print("\n[draft_booking_confirmation]")
    print(draft_booking_confirmation(client, MESSAGE, start, end))

    print("\n[draft_time_unavailable]")
    print(draft_time_unavailable(client, MESSAGE, start, end))

    print("\n[draft_slot_offer]")
    slots = [TimeSlot(start=hold.start, end=hold.end) for hold in CANDIDATE_HOLDS]
    print(draft_slot_offer(client, MESSAGE, slots))

    print("\n[draft_slot_confirmed]")
    print(draft_slot_confirmed(client, MESSAGE, CANDIDATE_HOLDS[0]))


if __name__ == "__main__":
    main()
