from datetime import datetime, timezone
from unittest.mock import MagicMock

from gcalendar.freebusy import get_calendar_timezone, is_slot_free, query_busy_intervals


def _service_with_events_list(response):
    service = MagicMock()
    service.events.return_value.list.return_value.execute.return_value = response
    return service


def _service_with_busy(busy_periods):
    service = MagicMock()
    service.freebusy.return_value.query.return_value.execute.return_value = {
        "calendars": {"primary": {"busy": busy_periods}}
    }
    return service


def test_get_calendar_timezone_reads_time_zone_field():
    service = _service_with_events_list({"timeZone": "Asia/Kolkata"})

    result = get_calendar_timezone(service)

    assert result == "Asia/Kolkata"
    service.events.return_value.list.assert_called_once_with(
        calendarId="primary", maxResults=1
    )


def test_query_busy_intervals_builds_correct_request_body():
    service = _service_with_busy([])
    time_min = datetime(2026, 7, 6, 9, 0, tzinfo=timezone.utc)
    time_max = datetime(2026, 7, 6, 17, 0, tzinfo=timezone.utc)

    query_busy_intervals(service, time_min, time_max, "Asia/Kolkata")

    service.freebusy.return_value.query.assert_called_once_with(
        body={
            "timeMin": time_min.isoformat(),
            "timeMax": time_max.isoformat(),
            "timeZone": "Asia/Kolkata",
            "items": [{"id": "primary"}],
        }
    )


def test_query_busy_intervals_parses_busy_periods_into_datetimes():
    service = _service_with_busy(
        [{"start": "2026-07-06T10:00:00Z", "end": "2026-07-06T11:00:00Z"}]
    )

    result = query_busy_intervals(
        service,
        datetime(2026, 7, 6, 9, 0, tzinfo=timezone.utc),
        datetime(2026, 7, 6, 17, 0, tzinfo=timezone.utc),
        "UTC",
    )

    assert result == [
        (
            datetime(2026, 7, 6, 10, 0, tzinfo=timezone.utc),
            datetime(2026, 7, 6, 11, 0, tzinfo=timezone.utc),
        )
    ]


def test_query_busy_intervals_sorts_and_merges_overlapping_periods():
    service = _service_with_busy(
        [
            {"start": "2026-07-06T14:00:00Z", "end": "2026-07-06T15:00:00Z"},
            {"start": "2026-07-06T10:00:00Z", "end": "2026-07-06T11:30:00Z"},
            {"start": "2026-07-06T11:00:00Z", "end": "2026-07-06T12:00:00Z"},
        ]
    )

    result = query_busy_intervals(
        service,
        datetime(2026, 7, 6, 9, 0, tzinfo=timezone.utc),
        datetime(2026, 7, 6, 17, 0, tzinfo=timezone.utc),
        "UTC",
    )

    assert result == [
        (
            datetime(2026, 7, 6, 10, 0, tzinfo=timezone.utc),
            datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc),
        ),
        (
            datetime(2026, 7, 6, 14, 0, tzinfo=timezone.utc),
            datetime(2026, 7, 6, 15, 0, tzinfo=timezone.utc),
        ),
    ]


def test_is_slot_free_true_when_no_overlap():
    service = _service_with_busy(
        [{"start": "2026-07-06T14:00:00Z", "end": "2026-07-06T15:00:00Z"}]
    )

    result = is_slot_free(
        service,
        datetime(2026, 7, 6, 10, 0, tzinfo=timezone.utc),
        datetime(2026, 7, 6, 10, 30, tzinfo=timezone.utc),
        "UTC",
    )

    assert result is True


def test_is_slot_free_false_when_overlapping():
    service = _service_with_busy(
        [{"start": "2026-07-06T10:00:00Z", "end": "2026-07-06T11:00:00Z"}]
    )

    result = is_slot_free(
        service,
        datetime(2026, 7, 6, 10, 15, tzinfo=timezone.utc),
        datetime(2026, 7, 6, 10, 45, tzinfo=timezone.utc),
        "UTC",
    )

    assert result is False
