"""Manual end-to-end check of the llm package against the real Gemini API.

Run this with a real GEMINI_API_KEY in .env (see config.py). For each
intent, classifies one hand-written email and then drafts its natural
follow-up reply, one API call at a time with a pause in between to stay
under the free tier's per-minute rate limit. Prints results for human
review — no assertions, no Gmail/Calendar API calls (llm/ is pure).
"""

import time
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

# Gemini's free tier allows only a few requests/minute (and a low daily
# cap); space calls out comfortably under that instead of bursting
# through the whole script.
SLEEP_SECONDS = 15

TZ = ZoneInfo("America/New_York")
NOW = datetime(2026, 7, 7, 9, 0, tzinfo=TZ)  # a Tuesday

# llm/ is pure (no Gmail API calls), so this stands in for the real
# gmail.profile.get_display_name() value agent.py fetches at runtime.
YOUR_NAME = "Mohammed Rishin Poolat"

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


def main() -> None:
    client = get_client()

    start, end = (
        NOW + timedelta(days=1, hours=1),
        NOW + timedelta(days=1, hours=1, minutes=30),
    )

    print("[propose_time]")
    result = classify_email(
        client,
        MESSAGE,
        "Hi, could we meet this Thursday at 2pm? Let me know if that works.",
        NOW,
        [],
    )
    print(f"  classify -> {result}")
    time.sleep(SLEEP_SECONDS)

    print("  draft_booking_confirmation ->")
    print(draft_booking_confirmation(client, MESSAGE, start, end, YOUR_NAME))
    time.sleep(SLEEP_SECONDS)

    print("  draft_time_unavailable ->")
    print(draft_time_unavailable(client, MESSAGE, start, end, YOUR_NAME))
    time.sleep(SLEEP_SECONDS)

    print("\n[ask_availability]")
    result = classify_email(
        client,
        MESSAGE,
        "Hi, I'd love to chat sometime next week. What does your availability look like?",
        NOW,
        [],
    )
    print(f"  classify -> {result}")
    time.sleep(SLEEP_SECONDS)

    print("  draft_slot_offer ->")
    slots = [TimeSlot(start=hold.start, end=hold.end) for hold in CANDIDATE_HOLDS]
    print(draft_slot_offer(client, MESSAGE, slots, YOUR_NAME))
    time.sleep(SLEEP_SECONDS)

    print("\n[irrelevant]")
    result = classify_email(
        client,
        MESSAGE,
        "50% off all products this week only! Click here to unsubscribe.",
        NOW,
        [],
    )
    print(f"  classify -> {result}")
    time.sleep(SLEEP_SECONDS)

    print("\n[accept_slot]")
    result = classify_email(
        client,
        MESSAGE,
        "Option 2 works great for me, see you then!",
        NOW,
        CANDIDATE_HOLDS,
    )
    print(f"  classify -> {result}")
    time.sleep(SLEEP_SECONDS)

    if result.matched_hold is not None:
        print("  draft_slot_confirmed ->")
        print(draft_slot_confirmed(client, MESSAGE, result.matched_hold, YOUR_NAME))


if __name__ == "__main__":
    main()
