from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from gcalendar.slots import TimeSlot, find_open_slots

# Fixed reference week: 2024-01-01 is a Monday.
MON, TUE, WED, THU, FRI, SAT, SUN = range(1, 8)


def _service(busy_periods=None):
    service = MagicMock()
    service.events.return_value.list.return_value.execute.return_value = {
        "timeZone": "UTC"
    }
    service.freebusy.return_value.query.return_value.execute.return_value = {
        "calendars": {"primary": {"busy": busy_periods or []}}
    }
    return service


def _dt(day, hour, minute=0):
    return datetime(2024, 1, day, hour, minute, tzinfo=timezone.utc)


def test_fully_free_calendar_returns_exactly_count_slots_from_9am():
    service = _service()

    slots = find_open_slots(service, count=5, now=_dt(MON, 8, 0))

    assert len(slots) == 5
    assert slots[0] == TimeSlot(start=_dt(MON, 9, 0), end=_dt(MON, 9, 30))


def test_friday_afternoon_skips_weekend_to_monday():
    service = _service()

    slots = find_open_slots(service, count=10, now=_dt(FRI, 16, 0))

    assert slots[0] == TimeSlot(start=_dt(FRI, 16, 0), end=_dt(FRI, 16, 30))
    assert slots[1] == TimeSlot(start=_dt(FRI, 16, 30), end=_dt(FRI, 17, 0))
    assert slots[2] == TimeSlot(start=_dt(8, 9, 0), end=_dt(8, 9, 30))


def test_mid_morning_now_rounds_up_to_next_30_minute_mark():
    service = _service()

    slots = find_open_slots(service, count=1, now=_dt(TUE, 11, 47))

    assert slots[0].start == _dt(TUE, 12, 0)


def test_busy_interval_mid_window_splits_slots_around_it():
    service = _service(
        busy_periods=[{"start": "2024-01-02T10:00:00Z", "end": "2024-01-02T11:00:00Z"}]
    )

    slots = find_open_slots(service, count=10, now=_dt(TUE, 8, 0))

    assert TimeSlot(start=_dt(TUE, 9, 0), end=_dt(TUE, 9, 30)) in slots
    assert TimeSlot(start=_dt(TUE, 11, 0), end=_dt(TUE, 11, 30)) in slots
    assert not any(_dt(TUE, 10, 0) <= slot.start < _dt(TUE, 11, 0) for slot in slots)


def test_fully_busy_day_is_skipped_to_next_business_day():
    service = _service(
        busy_periods=[{"start": "2024-01-01T09:00:00Z", "end": "2024-01-01T17:00:00Z"}]
    )

    slots = find_open_slots(service, count=1, now=_dt(MON, 8, 0))

    assert slots[0].start == _dt(TUE, 9, 0)


def test_now_after_5pm_excludes_today():
    service = _service()

    slots = find_open_slots(service, count=1, now=_dt(TUE, 18, 0))

    assert slots[0].start == _dt(WED, 9, 0)


def test_fully_busy_lookahead_window_returns_fewer_than_count():
    service = _service(
        busy_periods=[{"start": "2024-01-01T09:00:00Z", "end": "2024-01-05T17:00:00Z"}]
    )

    slots = find_open_slots(service, count=5, now=_dt(MON, 8, 0))

    assert slots == []


def test_exactly_one_freebusy_query_call():
    service = _service()

    find_open_slots(service, count=5, now=_dt(MON, 8, 0))

    service.freebusy.return_value.query.return_value.execute.assert_called_once()


def test_naive_now_raises_instead_of_silently_using_local_timezone():
    service = _service()

    with pytest.raises(ValueError, match="timezone-aware"):
        find_open_slots(service, count=1, now=datetime(2024, 1, 1, 8, 0))
