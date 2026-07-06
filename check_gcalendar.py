"""Manual end-to-end check of the gcalendar package against a real calendar.

Run this against a real Google Calendar once auth is set up (see
check_auth.py). Exercises timezone lookup, open-slot finding, confirmed
booking, freebusy, and the tentative-hold lifecycle (create, expire,
confirm-and-release-siblings). Cleans up every event it creates.
"""

from gcalendar.client import get_service
from gcalendar.events import (
    book_event,
    confirm_hold,
    create_hold,
    expire_stale_holds,
    list_holds,
)
from gcalendar.freebusy import get_calendar_timezone, is_slot_free
from gcalendar.slots import find_open_slots

TEST_ATTENDEE = "check-gcalendar-manual-test@example.com"
TEST_THREAD_ID = "check-gcalendar-manual-test"


def main() -> None:
    service = get_service()

    tz_name = get_calendar_timezone(service)
    print(f"Calendar timezone: {tz_name}")

    slots = find_open_slots(service)
    print(f"\n{len(slots)} open slot(s):")
    for slot in slots:
        print(f"- {slot.start} to {slot.end}")

    if not slots:
        print("No open slots found — skipping booking/hold checks.")
        return

    first_slot = slots[0]
    booked = book_event(
        service,
        "check_gcalendar test booking",
        first_slot.start,
        first_slot.end,
        TEST_ATTENDEE,
    )
    print(f"\nBooked confirmed event id={booked['id']}")
    still_free = is_slot_free(service, first_slot.start, first_slot.end, tz_name)
    print(f"is_slot_free() on the just-booked slot (expect False): {still_free}")

    hold_a = create_hold(
        service,
        "check_gcalendar hold A",
        slots[1].start,
        slots[1].end,
        TEST_ATTENDEE,
        TEST_THREAD_ID,
    )
    hold_b = create_hold(
        service,
        "check_gcalendar hold B",
        slots[2].start,
        slots[2].end,
        TEST_ATTENDEE,
        TEST_THREAD_ID,
    )
    print(f"\nCreated holds: {hold_a['id']}, {hold_b['id']}")

    # WARNING: expire_stale_holds() sweeps every stale hold on the calendar,
    # not just the two created above. Only run this script against a
    # calendar with no real pending holds from the live agent.
    deleted = expire_stale_holds(service, max_age_hours=0)
    print(f"expire_stale_holds(max_age_hours=0) deleted: {deleted}")

    hold_c = create_hold(
        service,
        "check_gcalendar hold C",
        slots[3].start,
        slots[3].end,
        TEST_ATTENDEE,
        TEST_THREAD_ID,
    )
    hold_d = create_hold(
        service,
        "check_gcalendar hold D",
        slots[4].start,
        slots[4].end,
        TEST_ATTENDEE,
        TEST_THREAD_ID,
    )
    print(f"Created holds: {hold_c['id']}, {hold_d['id']}")

    confirm_hold(service, TEST_THREAD_ID, hold_c["id"])
    remaining = list_holds(service, thread_id=TEST_THREAD_ID)
    print(
        f"After confirm_hold, remaining holds for thread (expect only hold_c): {remaining}"
    )

    service.events().delete(
        calendarId="primary", eventId=booked["id"], sendUpdates="none"
    ).execute()
    service.events().delete(
        calendarId="primary", eventId=hold_c["id"], sendUpdates="none"
    ).execute()
    print("\nCleaned up booked event and confirmed hold.")


if __name__ == "__main__":
    main()
