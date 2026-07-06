from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from googleapiclient.errors import HttpError

from gcalendar.events import (
    book_event,
    confirm_hold,
    create_hold,
    expire_stale_holds,
    list_holds,
)


def _service():
    return MagicMock()


def _http_error(status):
    response = MagicMock()
    response.status = status
    return HttpError(response, b"{}")


def _hold_item(
    event_id,
    thread_id,
    created,
    start="2024-01-02T09:00:00Z",
    end="2024-01-02T09:30:00Z",
):
    return {
        "id": event_id,
        "start": {"dateTime": start},
        "end": {"dateTime": end},
        "created": created,
        "extendedProperties": {
            "private": {"scheduler_hold": "true", "scheduler_thread_id": thread_id}
        },
    }


def test_book_event_creates_confirmed_event_without_notifying():
    service = _service()
    start = datetime(2024, 1, 2, 9, 0, tzinfo=timezone.utc)
    end = datetime(2024, 1, 2, 9, 30, tzinfo=timezone.utc)

    book_event(service, "Intro call", start, end, "sender@example.com")

    service.events.return_value.insert.assert_called_once_with(
        calendarId="primary",
        body={
            "summary": "Intro call",
            "status": "confirmed",
            "start": {"dateTime": start.isoformat()},
            "end": {"dateTime": end.isoformat()},
            "attendees": [{"email": "sender@example.com"}],
        },
        sendUpdates="none",
    )


def test_create_hold_tags_extended_properties_and_suppresses_notification():
    service = _service()
    start = datetime(2024, 1, 2, 9, 0, tzinfo=timezone.utc)
    end = datetime(2024, 1, 2, 9, 30, tzinfo=timezone.utc)

    create_hold(service, "Intro call", start, end, "sender@example.com", "thread-1")

    service.events.return_value.insert.assert_called_once_with(
        calendarId="primary",
        body={
            "summary": "Intro call",
            "status": "tentative",
            "start": {"dateTime": start.isoformat()},
            "end": {"dateTime": end.isoformat()},
            "attendees": [{"email": "sender@example.com"}],
            "extendedProperties": {
                "private": {"scheduler_hold": "true", "scheduler_thread_id": "thread-1"}
            },
        },
        sendUpdates="none",
    )


def test_list_holds_without_thread_id_filters_on_hold_flag_only():
    service = _service()
    service.events.return_value.list.return_value.execute.return_value = {"items": []}

    list_holds(service)

    service.events.return_value.list.assert_called_once_with(
        calendarId="primary", privateExtendedProperty=["scheduler_hold=true"]
    )


def test_list_holds_with_thread_id_ands_both_constraints():
    service = _service()
    service.events.return_value.list.return_value.execute.return_value = {"items": []}

    list_holds(service, thread_id="thread-1")

    service.events.return_value.list.assert_called_once_with(
        calendarId="primary",
        privateExtendedProperty=["scheduler_hold=true", "scheduler_thread_id=thread-1"],
    )


def test_list_holds_parses_items_including_z_suffixed_created_timestamp():
    service = _service()
    service.events.return_value.list.return_value.execute.return_value = {
        "items": [_hold_item("evt-1", "thread-1", "2024-01-01T00:00:00.000Z")]
    }

    holds = list_holds(service, thread_id="thread-1")

    assert len(holds) == 1
    assert holds[0].id == "evt-1"
    assert holds[0].thread_id == "thread-1"
    assert holds[0].created == datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    assert holds[0].start == datetime(2024, 1, 2, 9, 0, tzinfo=timezone.utc)
    assert holds[0].end == datetime(2024, 1, 2, 9, 30, tzinfo=timezone.utc)


def test_confirm_hold_patches_target_and_deletes_only_siblings():
    service = _service()
    service.events.return_value.list.return_value.execute.return_value = {
        "items": [
            _hold_item("evt-1", "thread-1", "2024-01-01T00:00:00Z"),
            _hold_item("evt-2", "thread-1", "2024-01-01T00:00:00Z"),
            _hold_item("evt-3", "thread-1", "2024-01-01T00:00:00Z"),
        ]
    }

    confirm_hold(service, "thread-1", "evt-2")

    service.events.return_value.patch.assert_called_once_with(
        calendarId="primary",
        eventId="evt-2",
        body={
            "status": "confirmed",
            "extendedProperties": {"private": {"scheduler_hold": "false"}},
        },
        sendUpdates="none",
    )
    deleted_ids = {
        call.kwargs["eventId"]
        for call in service.events.return_value.delete.call_args_list
    }
    assert deleted_ids == {"evt-1", "evt-3"}


def test_confirm_hold_with_no_siblings_deletes_nothing():
    service = _service()
    service.events.return_value.list.return_value.execute.return_value = {
        "items": [_hold_item("evt-1", "thread-1", "2024-01-01T00:00:00Z")]
    }

    confirm_hold(service, "thread-1", "evt-1")

    service.events.return_value.delete.assert_not_called()


def test_confirm_hold_swallows_404_on_sibling_delete_and_continues():
    service = _service()
    service.events.return_value.list.return_value.execute.return_value = {
        "items": [
            _hold_item("evt-1", "thread-1", "2024-01-01T00:00:00Z"),
            _hold_item("evt-2", "thread-1", "2024-01-01T00:00:00Z"),
            _hold_item("evt-3", "thread-1", "2024-01-01T00:00:00Z"),
        ]
    }
    service.events.return_value.delete.return_value.execute.side_effect = [
        _http_error(404),
        None,
    ]

    confirm_hold(service, "thread-1", "evt-2")

    assert service.events.return_value.delete.return_value.execute.call_count == 2


def test_expire_stale_holds_deletes_only_holds_older_than_cutoff():
    service = _service()
    now = datetime(2024, 1, 10, 0, 0, tzinfo=timezone.utc)
    service.events.return_value.list.return_value.execute.return_value = {
        "items": [
            _hold_item(
                "stale",
                "thread-1",
                (now - timedelta(hours=49)).isoformat().replace("+00:00", "Z"),
            ),
            _hold_item(
                "fresh",
                "thread-2",
                (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
            ),
        ]
    }

    deleted = expire_stale_holds(service, max_age_hours=48, now=now)

    assert deleted == ["stale"]
    service.events.return_value.delete.assert_called_once_with(
        calendarId="primary", eventId="stale", sendUpdates="none"
    )


def test_expire_stale_holds_with_no_holds_is_a_noop():
    service = _service()
    service.events.return_value.list.return_value.execute.return_value = {"items": []}

    deleted = expire_stale_holds(service)

    assert deleted == []
    service.events.return_value.delete.assert_not_called()


def test_expire_stale_holds_swallows_404_mid_sweep():
    service = _service()
    now = datetime(2024, 1, 10, 0, 0, tzinfo=timezone.utc)
    service.events.return_value.list.return_value.execute.return_value = {
        "items": [
            _hold_item(
                "stale-1",
                "thread-1",
                (now - timedelta(hours=49)).isoformat().replace("+00:00", "Z"),
            ),
            _hold_item(
                "stale-2",
                "thread-2",
                (now - timedelta(hours=50)).isoformat().replace("+00:00", "Z"),
            ),
        ]
    }
    service.events.return_value.delete.return_value.execute.side_effect = [
        _http_error(404),
        None,
    ]

    deleted = expire_stale_holds(service, max_age_hours=48, now=now)

    assert deleted == ["stale-1", "stale-2"]
