"""Booking confirmed events and managing tentative holds."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from googleapiclient.errors import HttpError

from gcalendar.client import CALENDAR_ID

HOLD_KEY = "scheduler_hold"
THREAD_KEY = "scheduler_thread_id"
HOLD_MAX_AGE_HOURS = 48


@dataclass
class Hold:
    id: str
    thread_id: str
    start: datetime
    end: datetime
    created: datetime


def book_event(
    service: Any, summary: str, start: datetime, end: datetime, attendee_email: str
) -> Any:
    """Create a confirmed calendar event with the sender as attendee (no auto-email)."""
    body = {
        "summary": summary,
        "status": "confirmed",
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": end.isoformat()},
        "attendees": [{"email": attendee_email}],
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
    """Confirm one hold for `thread_id`; delete its sibling holds (404-safe)."""
    siblings = list_holds(service, thread_id=thread_id)
    service.events().patch(
        calendarId=CALENDAR_ID,
        eventId=event_id,
        body={
            "status": "confirmed",
            "extendedProperties": {"private": {HOLD_KEY: "false"}},
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


def _delete_event_ignoring_404(service: Any, event_id: str) -> None:
    try:
        service.events().delete(
            calendarId=CALENDAR_ID, eventId=event_id, sendUpdates="none"
        ).execute()
    except HttpError as error:
        if error.resp.status != 404:
            raise
