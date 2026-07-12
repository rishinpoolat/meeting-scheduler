from datetime import datetime, timedelta, timezone
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


def _slot(day, hour, minute=0):
    start = _dt(day, hour, minute)
    return TimeSlot(start=start, end=start + timedelta(minutes=30))


def test_fully_free_calendar_spreads_slots_across_half_days():
    service = _service()

    slots = find_open_slots(service, count=5, now=_dt(MON, 8, 0))

    assert slots == [
        _slot(MON, 9, 0),
        _slot(MON, 13, 0),
        _slot(TUE, 9, 0),
        _slot(TUE, 13, 0),
        _slot(WED, 9, 0),
    ]


def test_mid_morning_now_rounds_up_but_stays_in_morning_half():
    service = _service()

    slots = find_open_slots(service, count=1, now=_dt(TUE, 11, 47))

    assert slots == [_slot(TUE, 12, 0)]


def test_mid_afternoon_now_excludes_morning_and_rounds_up_within_afternoon():
    service = _service()

    slots = find_open_slots(service, count=1, now=_dt(TUE, 14, 17))

    assert slots == [_slot(TUE, 14, 30)]


def test_now_exactly_at_midday_boundary_excludes_morning():
    service = _service()

    slots = find_open_slots(service, count=2, now=_dt(TUE, 13, 0))

    assert slots == [_slot(TUE, 13, 0), _slot(WED, 9, 0)]


def test_now_after_5pm_excludes_today():
    service = _service()

    slots = find_open_slots(service, count=1, now=_dt(TUE, 18, 0))

    assert slots == [_slot(WED, 9, 0)]


def test_friday_afternoon_skips_weekend_to_monday_morning_not_afternoon():
    service = _service()

    slots = find_open_slots(service, count=3, now=_dt(FRI, 16, 0))

    assert slots == [_slot(FRI, 16, 0), _slot(8, 9, 0), _slot(8, 13, 0)]


def test_busy_full_morning_skips_to_afternoon_next_day_starts_fresh():
    service = _service(
        busy_periods=[{"start": "2024-01-01T09:00:00Z", "end": "2024-01-01T13:00:00Z"}]
    )

    slots = find_open_slots(service, count=3, now=_dt(MON, 8, 0))

    assert slots == [_slot(MON, 13, 0), _slot(TUE, 9, 0), _slot(TUE, 13, 0)]


def test_partial_busy_block_shifts_chosen_slot_later_within_same_half():
    service = _service(
        busy_periods=[{"start": "2024-01-02T09:00:00Z", "end": "2024-01-02T10:00:00Z"}]
    )

    slots = find_open_slots(service, count=1, now=_dt(TUE, 8, 0))

    assert slots == [_slot(TUE, 10, 0)]


def test_fully_busy_day_skips_both_halves_to_next_business_day():
    service = _service(
        busy_periods=[{"start": "2024-01-01T09:00:00Z", "end": "2024-01-01T17:00:00Z"}]
    )

    slots = find_open_slots(service, count=1, now=_dt(MON, 8, 0))

    assert slots == [_slot(TUE, 9, 0)]


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


def test_count_zero_returns_empty_list():
    service = _service()

    slots = find_open_slots(service, count=0, now=_dt(MON, 8, 0))

    assert slots == []


def test_count_negative_returns_empty_list():
    service = _service()

    slots = find_open_slots(service, count=-1, now=_dt(MON, 8, 0))

    assert slots == []


def test_now_exactly_at_5pm_excludes_today():
    service = _service()

    slots = find_open_slots(service, count=1, now=_dt(TUE, 17, 0))

    assert slots == [_slot(WED, 9, 0)]


def test_earliest_after_now_pushes_start_later():
    service = _service()

    slots = find_open_slots(
        service, count=2, now=_dt(MON, 8, 0), earliest=_dt(WED, 0, 0)
    )

    assert slots == [_slot(WED, 9, 0), _slot(WED, 13, 0)]


def test_earliest_before_now_is_clamped_to_now():
    service = _service()

    slots = find_open_slots(
        service, count=1, now=_dt(TUE, 11, 47), earliest=_dt(MON, 8, 0)
    )

    assert slots == [_slot(TUE, 12, 0)]


def test_earliest_mid_day_applies_same_rounding_as_now():
    service = _service()

    slots = find_open_slots(
        service, count=1, now=_dt(MON, 8, 0), earliest=_dt(TUE, 14, 17)
    )

    assert slots == [_slot(TUE, 14, 30)]


def test_earliest_on_weekend_rolls_to_next_business_day_morning():
    service = _service()

    slots = find_open_slots(
        service, count=1, now=_dt(FRI, 8, 0), earliest=_dt(SAT, 10, 0)
    )

    assert slots == [_slot(8, 9, 0)]


def test_earliest_far_in_future_still_returns_full_count():
    service = _service()
    earliest = datetime(2024, 2, 1, 8, 0, tzinfo=timezone.utc)  # a Thursday

    slots = find_open_slots(service, count=5, now=_dt(MON, 8, 0), earliest=earliest)

    assert len(slots) == 5
    assert all(slot.start >= earliest for slot in slots)
    assert slots[0] == TimeSlot(
        start=datetime(2024, 2, 1, 9, 0, tzinfo=timezone.utc),
        end=datetime(2024, 2, 1, 9, 30, tzinfo=timezone.utc),
    )


def test_naive_earliest_raises_instead_of_silently_using_local_timezone():
    service = _service()

    with pytest.raises(ValueError, match="timezone-aware"):
        find_open_slots(
            service, count=1, now=_dt(MON, 8, 0), earliest=datetime(2024, 1, 3, 0, 0)
        )


def test_earliest_defaults_to_none_preserves_existing_behavior():
    service = _service()

    slots = find_open_slots(service, count=5, now=_dt(MON, 8, 0))

    assert slots == [
        _slot(MON, 9, 0),
        _slot(MON, 13, 0),
        _slot(TUE, 9, 0),
        _slot(TUE, 13, 0),
        _slot(WED, 9, 0),
    ]
