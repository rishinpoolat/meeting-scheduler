"""Open-slot finding across the next few business days."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from gcalendar.freebusy import get_calendar_timezone, query_busy_intervals

BUSINESS_START_HOUR = 9
BUSINESS_END_HOUR = 17
BUSINESS_WEEKDAYS = range(0, 5)  # Monday-Friday
LOOKAHEAD_BUSINESS_DAYS = 5
SLOT_DURATION = timedelta(minutes=30)


@dataclass
class TimeSlot:
    start: datetime
    end: datetime


def find_open_slots(
    service: Any, count: int = 5, now: datetime | None = None
) -> list[TimeSlot]:
    """Return up to `count` free 30-min slots in the next 5 business days, 9am-5pm."""
    if now is not None and now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    tz_name = get_calendar_timezone(service)
    tz = ZoneInfo(tz_name)
    current = (now or datetime.now(tz)).astimezone(tz)

    windows = _business_hour_windows(current, tz)
    if not windows:
        return []

    busy_intervals = query_busy_intervals(
        service, windows[0][0], windows[-1][1], tz_name
    )

    slots: list[TimeSlot] = []
    for window_start, window_end in windows:
        for free_start, free_end in _subtract_busy(
            window_start, window_end, busy_intervals
        ):
            slots.extend(_chunk_into_slots(free_start, free_end, count - len(slots)))
            if len(slots) >= count:
                return slots
    return slots


def _business_hour_windows(
    current: datetime, tz: ZoneInfo
) -> list[tuple[datetime, datetime]]:
    windows: list[tuple[datetime, datetime]] = []
    day: date = current.date()
    is_first_business_day = True
    while len(windows) < LOOKAHEAD_BUSINESS_DAYS:
        if day.weekday() in BUSINESS_WEEKDAYS:
            day_start = datetime.combine(day, time(BUSINESS_START_HOUR, 0), tzinfo=tz)
            day_end = datetime.combine(day, time(BUSINESS_END_HOUR, 0), tzinfo=tz)
            if is_first_business_day:
                is_first_business_day = False
                if current > day_end:
                    day += timedelta(days=1)
                    continue
                if current > day_start:
                    day_start = _round_up_to_slot(current)
            windows.append((day_start, day_end))
        day += timedelta(days=1)
    return windows


def _round_up_to_slot(moment: datetime) -> datetime:
    discard = timedelta(
        minutes=moment.minute % 30,
        seconds=moment.second,
        microseconds=moment.microsecond,
    )
    if discard == timedelta():
        return moment
    return moment - discard + timedelta(minutes=30)


def _subtract_busy(
    window_start: datetime,
    window_end: datetime,
    busy_intervals: list[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    free: list[tuple[datetime, datetime]] = []
    cursor = window_start
    for busy_start, busy_end in busy_intervals:
        if busy_end <= cursor or busy_start >= window_end:
            continue
        if busy_start > cursor:
            free.append((cursor, min(busy_start, window_end)))
        cursor = max(cursor, busy_end)
        if cursor >= window_end:
            break
    if cursor < window_end:
        free.append((cursor, window_end))
    return free


def _chunk_into_slots(
    free_start: datetime, free_end: datetime, remaining: int
) -> list[TimeSlot]:
    slots: list[TimeSlot] = []
    cursor = _round_up_to_slot(free_start)
    while len(slots) < remaining and cursor + SLOT_DURATION <= free_end:
        slots.append(TimeSlot(start=cursor, end=cursor + SLOT_DURATION))
        cursor += SLOT_DURATION
    return slots
