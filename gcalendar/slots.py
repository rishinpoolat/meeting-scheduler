"""Open-slot finding across the next few business days."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from gcalendar.freebusy import get_calendar_timezone, query_busy_intervals

BUSINESS_START_HOUR = 9
MIDDAY_SPLIT_HOUR = 13
BUSINESS_END_HOUR = 17
BUSINESS_WEEKDAYS = range(0, 5)  # Monday-Friday
LOOKAHEAD_BUSINESS_DAYS = 5
SLOT_DURATION = timedelta(minutes=30)


@dataclass
class TimeSlot:
    start: datetime
    end: datetime


def find_open_slots(
    service: Any,
    count: int = 5,
    now: datetime | None = None,
    earliest: datetime | None = None,
) -> list[TimeSlot]:
    """Return up to `count` free 30-min slots, at most one per half-day
    (morning, afternoon), across the next 5 business days, 9am-5pm.

    `earliest`, if given, pushes the starting point later than `now`
    when it's further in the future - it never pulls the start earlier
    than `now` itself.
    """
    if now is not None and now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    if earliest is not None and earliest.tzinfo is None:
        raise ValueError("earliest must be timezone-aware")
    if count <= 0:
        return []
    tz_name = get_calendar_timezone(service)
    tz = ZoneInfo(tz_name)
    current = (now or datetime.now(tz)).astimezone(tz)
    if earliest is not None:
        current = max(current, earliest.astimezone(tz))

    windows = _half_day_windows(current, tz)
    if not windows:
        return []

    busy_intervals = query_busy_intervals(
        service, windows[0][0], windows[-1][1], tz_name
    )

    slots: list[TimeSlot] = []
    for window_start, window_end in windows:
        if len(slots) >= count:
            break
        slot = _first_slot_in_window(window_start, window_end, busy_intervals)
        if slot is not None:
            slots.append(slot)
    return slots


def _half_day_windows(
    current: datetime, tz: ZoneInfo
) -> list[tuple[datetime, datetime]]:
    windows: list[tuple[datetime, datetime]] = []
    day: date = current.date()
    is_first_business_day = True
    business_days_used = 0
    while business_days_used < LOOKAHEAD_BUSINESS_DAYS:
        if day.weekday() in BUSINESS_WEEKDAYS:
            morning_start = datetime.combine(
                day, time(BUSINESS_START_HOUR, 0), tzinfo=tz
            )
            split = datetime.combine(day, time(MIDDAY_SPLIT_HOUR, 0), tzinfo=tz)
            day_end = datetime.combine(day, time(BUSINESS_END_HOUR, 0), tzinfo=tz)
            day_windows = [(morning_start, split), (split, day_end)]
            if is_first_business_day:
                is_first_business_day = False
                day_windows = [
                    (
                        _round_up_to_slot(current)
                        if current > half_start
                        else half_start,
                        half_end,
                    )
                    for half_start, half_end in day_windows
                    if current < half_end
                ]
                if not day_windows:
                    day += timedelta(days=1)
                    continue
            windows.extend(day_windows)
            business_days_used += 1
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


def _first_slot_in_window(
    window_start: datetime,
    window_end: datetime,
    busy_intervals: list[tuple[datetime, datetime]],
) -> TimeSlot | None:
    for free_start, free_end in _subtract_busy(
        window_start, window_end, busy_intervals
    ):
        slot_start = _round_up_to_slot(free_start)
        if slot_start + SLOT_DURATION <= free_end:
            return TimeSlot(start=slot_start, end=slot_start + SLOT_DURATION)
    return None
