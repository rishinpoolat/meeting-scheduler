"""Booking confirmed events and managing tentative holds."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from googleapiclient.errors import HttpError

from gcalendar.client import CALENDAR_ID

HOLD_KEY = "scheduler_hold"
THREAD_KEY = "scheduler_thread_id"
BOOKING_KEY = "scheduler_booking"
HOLD_MAX_AGE_HOURS = 48
BOOKING_SEARCH_MAX_RESULTS = 250


@dataclass
class Hold:
    id: str
    thread_id: str
    start: datetime
    end: datetime
    created: datetime


@dataclass
class Booking:
    id: str
    thread_id: str | None
    start: datetime
    end: datetime


def book_event(
    service: Any,
    summary: str,
    start: datetime,
    end: datetime,
    attendee_email: str,
    thread_id: str,
) -> Any:
    """Create a confirmed calendar event with the sender as attendee (no
    auto-email), tagged with `thread_id` so it can be found later for
    cancellation/rescheduling."""
    body = {
        "summary": summary,
        "status": "confirmed",
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": end.isoformat()},
        "attendees": [{"email": attendee_email}],
        "extendedProperties": {"private": {BOOKING_KEY: "true", THREAD_KEY: thread_id}},
    }
    return (
        service.events()
        .insert(calendarId=CALENDAR_ID, body=body, sendUpdates="none")
        .execute()
    )


def create_hold(
    service: Any,
    summary: str,
    start: datetime,
    end: datetime,
    attendee_email: str,
    thread_id: str,
) -> Any:
    """Create one tentative hold tagged with `thread_id` (no auto-email)."""
    body = {
        "summary": summary,
        "status": "tentative",
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": end.isoformat()},
        "attendees": [{"email": attendee_email}],
        "extendedProperties": {"private": {HOLD_KEY: "true", THREAD_KEY: thread_id}},
    }
    return (
        service.events()
        .insert(calendarId=CALENDAR_ID, body=body, sendUpdates="none")
        .execute()
    )


def list_holds(service: Any, thread_id: str | None = None) -> list[Hold]:
    """Return all tentative holds, or only those tagged with `thread_id`."""
    private_extended_property = [f"{HOLD_KEY}=true"]
    if thread_id is not None:
        private_extended_property.append(f"{THREAD_KEY}={thread_id}")
    response = (
        service.events()
        .list(calendarId=CALENDAR_ID, privateExtendedProperty=private_extended_property)
        .execute()
    )
    return [_to_hold(item) for item in response.get("items", [])]


def _to_hold(item: dict[str, Any]) -> Hold:
    private_props = item["extendedProperties"]["private"]
    return Hold(
        id=item["id"],
        thread_id=private_props[THREAD_KEY],
        start=datetime.fromisoformat(item["start"]["dateTime"]),
        end=datetime.fromisoformat(item["end"]["dateTime"]),
        created=datetime.fromisoformat(item["created"].replace("Z", "+00:00")),
    )


def confirm_hold(service: Any, thread_id: str, event_id: str) -> None:
    """Confirm one hold for `thread_id`; delete its sibling holds (404-safe).

    Also tags the now-confirmed event with `BOOKING_KEY` so it's findable
    by `find_booking_by_thread` the same as an event booked directly via
    `book_event` - both are "a confirmed meeting", regardless of which
    flow created them.
    """
    siblings = list_holds(service, thread_id=thread_id)
    service.events().patch(
        calendarId=CALENDAR_ID,
        eventId=event_id,
        body={
            "status": "confirmed",
            "extendedProperties": {"private": {HOLD_KEY: "false", BOOKING_KEY: "true"}},
        },
        sendUpdates="none",
    ).execute()
    for sibling in siblings:
        if sibling.id != event_id:
            _delete_event_ignoring_404(service, sibling.id)


def expire_stale_holds(
    service: Any, max_age_hours: int = HOLD_MAX_AGE_HOURS, now: datetime | None = None
) -> list[str]:
    """Delete holds older than `max_age_hours` with no confirmation; return deleted IDs (404-safe)."""
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(hours=max_age_hours)
    deleted_ids = []
    for hold in list_holds(service):
        if hold.created < cutoff:
            _delete_event_ignoring_404(service, hold.id)
            deleted_ids.append(hold.id)
    return deleted_ids


def find_booking_by_thread(service: Any, thread_id: str) -> Booking | None:
    """Return the confirmed booking tagged with `thread_id`, or None if
    none is tagged. If more than one matches, the one with the latest
    start wins."""
    response = (
        service.events()
        .list(
            calendarId=CALENDAR_ID,
            privateExtendedProperty=[
                f"{BOOKING_KEY}=true",
                f"{THREAD_KEY}={thread_id}",
            ],
        )
        .execute()
    )
    bookings = [_to_booking(item) for item in response.get("items", [])]
    if not bookings:
        return None
    return max(bookings, key=lambda booking: booking.start)


def find_booking_by_attendee(
    service: Any, attendee_email: str, now: datetime
) -> Booking | None:
    """Best-effort fallback for bookings made before booking-tagging
    existed: find exactly one upcoming confirmed event with a matching
    attendee, excluding holds and already booking-tagged events (those
    are covered by `find_booking_by_thread`). Zero or multiple matches
    return None - ambiguity is never guessed at.

    Only the first `BOOKING_SEARCH_MAX_RESULTS` upcoming events are
    considered (no `nextPageToken` follow-up) - a true duplicate match
    sitting past that page would be missed, silently turning a
    should-be-ambiguous case into a false unique match. Accepted at
    this project's calendar volume; revisit if that stops being true.
    """
    response = (
        service.events()
        .list(
            calendarId=CALENDAR_ID,
            timeMin=now.isoformat(),
            singleEvents=True,
            maxResults=BOOKING_SEARCH_MAX_RESULTS,
        )
        .execute()
    )
    target = attendee_email.lower()
    matches = []
    for item in response.get("items", []):
        if item.get("status") != "confirmed":
            continue
        private_props = item.get("extendedProperties", {}).get("private", {})
        if HOLD_KEY in private_props or BOOKING_KEY in private_props:
            continue
        attendee_emails = {
            a.get("email", "").lower() for a in item.get("attendees", [])
        }
        if target in attendee_emails:
            matches.append(_to_booking(item))
    if len(matches) != 1:
        return None
    return matches[0]


def _to_booking(item: dict[str, Any]) -> Booking:
    private_props = item.get("extendedProperties", {}).get("private", {})
    return Booking(
        id=item["id"],
        thread_id=private_props.get(THREAD_KEY),
        start=datetime.fromisoformat(item["start"]["dateTime"]),
        end=datetime.fromisoformat(item["end"]["dateTime"]),
    )


def cancel_booking(service: Any, event_id: str) -> None:
    """Delete a confirmed booking (404-safe)."""
    _delete_event_ignoring_404(service, event_id)


def reschedule_booking(
    service: Any, event_id: str, new_start: datetime, new_end: datetime
) -> None:
    """Move a confirmed booking to a new start/end, in place (no
    auto-email, tags/attendees untouched)."""
    service.events().patch(
        calendarId=CALENDAR_ID,
        eventId=event_id,
        body={
            "start": {"dateTime": new_start.isoformat()},
            "end": {"dateTime": new_end.isoformat()},
        },
        sendUpdates="none",
    ).execute()


def _delete_event_ignoring_404(service: Any, event_id: str) -> None:
    try:
        service.events().delete(
            calendarId=CALENDAR_ID, eventId=event_id, sendUpdates="none"
        ).execute()
    except HttpError as error:
        if error.resp.status != 404:
            raise
