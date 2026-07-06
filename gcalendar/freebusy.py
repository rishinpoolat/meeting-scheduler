"""Free/busy queries against the primary calendar."""

from datetime import datetime
from typing import Any

from gcalendar.client import CALENDAR_ID


def get_calendar_timezone(service: Any) -> str:
    """Return the primary calendar's IANA timezone name."""
    response = service.events().list(calendarId=CALENDAR_ID, maxResults=1).execute()
    timezone: str = response["timeZone"]
    return timezone


def query_busy_intervals(
    service: Any, time_min: datetime, time_max: datetime, tz_name: str
) -> list[tuple[datetime, datetime]]:
    """Return merged, sorted busy intervals on the primary calendar in [time_min, time_max)."""
    body = {
        "timeMin": time_min.isoformat(),
        "timeMax": time_max.isoformat(),
        "timeZone": tz_name,
        "items": [{"id": CALENDAR_ID}],
    }
    response = service.freebusy().query(body=body).execute()
    busy = response["calendars"][CALENDAR_ID]["busy"]
    intervals = sorted(
        (
            (
                datetime.fromisoformat(period["start"].replace("Z", "+00:00")),
                datetime.fromisoformat(period["end"].replace("Z", "+00:00")),
            )
            for period in busy
        ),
        key=lambda interval: interval[0],
    )
    return _merge_intervals(intervals)


def _merge_intervals(
    intervals: list[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    merged: list[tuple[datetime, datetime]] = []
    for start, end in intervals:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def is_slot_free(service: Any, start: datetime, end: datetime, tz_name: str) -> bool:
    """Return True if [start, end) has no busy time on the primary calendar."""
    busy_intervals = query_busy_intervals(service, start, end, tz_name)
    return not any(
        busy_start < end and start < busy_end for busy_start, busy_end in busy_intervals
    )
