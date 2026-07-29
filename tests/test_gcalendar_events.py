from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from googleapiclient.errors import HttpError

from gcalendar.events import (
    book_event,
    cancel_booking,
    confirm_hold,
    create_hold,
    expire_stale_holds,
    find_booking_by_attendee,
    find_booking_by_thread,
    list_holds,
    reschedule_booking,
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


def _booking_item(
    event_id,
    thread_id=None,
    status="confirmed",
    attendees=None,
    start="2024-01-02T09:00:00Z",
    end="2024-01-02T09:30:00Z",
    tagged=True,
):
    private = {}
    if tagged:
        private["scheduler_booking"] = "true"
        if thread_id is not None:
            private["scheduler_thread_id"] = thread_id
    return {
        "id": event_id,
        "status": status,
        "start": {"dateTime": start},
        "end": {"dateTime": end},
        "attendees": attendees or [],
        "extendedProperties": {"private": private},
    }


def test_book_event_creates_confirmed_event_tagged_with_thread_id():
    service = _service()
    start = datetime(2024, 1, 2, 9, 0, tzinfo=timezone.utc)
    end = datetime(2024, 1, 2, 9, 30, tzinfo=timezone.utc)

    book_event(service, "Intro call", start, end, "sender@example.com", "thread-1")

    service.events.return_value.insert.assert_called_once_with(
        calendarId="primary",
        body={
            "summary": "Intro call",
            "status": "confirmed",
            "start": {"dateTime": start.isoformat()},
            "end": {"dateTime": end.isoformat()},
            "attendees": [{"email": "sender@example.com"}],
            "extendedProperties": {
                "private": {
                    "scheduler_booking": "true",
                    "scheduler_thread_id": "thread-1",
                }
            },
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
            "extendedProperties": {
                "private": {"scheduler_hold": "false", "scheduler_booking": "true"}
            },
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


def test_find_booking_by_thread_queries_booking_and_thread_tags():
    service = _service()
    service.events.return_value.list.return_value.execute.return_value = {"items": []}

    find_booking_by_thread(service, "thread-1")

    service.events.return_value.list.assert_called_once_with(
        calendarId="primary",
        privateExtendedProperty=[
            "scheduler_booking=true",
            "scheduler_thread_id=thread-1",
        ],
    )


def test_find_booking_by_thread_returns_none_when_untagged():
    service = _service()
    service.events.return_value.list.return_value.execute.return_value = {"items": []}

    assert find_booking_by_thread(service, "thread-1") is None


def test_find_booking_by_thread_returns_match():
    service = _service()
    service.events.return_value.list.return_value.execute.return_value = {
        "items": [_booking_item("evt-1", thread_id="thread-1")]
    }

    booking = find_booking_by_thread(service, "thread-1")

    assert booking is not None
    assert booking.id == "evt-1"
    assert booking.thread_id == "thread-1"
    assert booking.start == datetime(2024, 1, 2, 9, 0, tzinfo=timezone.utc)
    assert booking.end == datetime(2024, 1, 2, 9, 30, tzinfo=timezone.utc)


def test_find_booking_by_thread_multiple_matches_picks_latest_start():
    service = _service()
    service.events.return_value.list.return_value.execute.return_value = {
        "items": [
            _booking_item(
                "earlier",
                thread_id="thread-1",
                start="2024-01-02T09:00:00Z",
                end="2024-01-02T09:30:00Z",
            ),
            _booking_item(
                "later",
                thread_id="thread-1",
                start="2024-01-03T09:00:00Z",
                end="2024-01-03T09:30:00Z",
            ),
        ]
    }

    booking = find_booking_by_thread(service, "thread-1")

    assert booking is not None
    assert booking.id == "later"


def test_find_booking_by_attendee_returns_single_match():
    service = _service()
    now = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    service.events.return_value.list.return_value.execute.return_value = {
        "items": [
            _booking_item(
                "evt-1",
                attendees=[{"email": "Sender@Example.com"}],
                tagged=False,
            )
        ]
    }

    booking = find_booking_by_attendee(service, "sender@example.com", now)

    assert booking is not None
    assert booking.id == "evt-1"
    assert booking.thread_id is None
    service.events.return_value.list.assert_called_once_with(
        calendarId="primary",
        timeMin=now.isoformat(),
        singleEvents=True,
        maxResults=250,
    )


def test_find_booking_by_attendee_returns_none_on_zero_matches():
    service = _service()
    now = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    service.events.return_value.list.return_value.execute.return_value = {
        "items": [
            _booking_item(
                "evt-1", attendees=[{"email": "other@example.com"}], tagged=False
            )
        ]
    }

    assert find_booking_by_attendee(service, "sender@example.com", now) is None


def test_find_booking_by_attendee_returns_none_on_multiple_matches():
    service = _service()
    now = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    service.events.return_value.list.return_value.execute.return_value = {
        "items": [
            _booking_item(
                "evt-1", attendees=[{"email": "sender@example.com"}], tagged=False
            ),
            _booking_item(
                "evt-2",
                attendees=[{"email": "sender@example.com"}],
                tagged=False,
                start="2024-01-05T09:00:00Z",
                end="2024-01-05T09:30:00Z",
            ),
        ]
    }

    assert find_booking_by_attendee(service, "sender@example.com", now) is None


def test_find_booking_by_attendee_excludes_holds_and_already_tagged_bookings():
    service = _service()
    now = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    hold_item = _hold_item("hold-1", "thread-1", "2024-01-01T00:00:00Z")
    hold_item["status"] = "tentative"
    hold_item["attendees"] = [{"email": "sender@example.com"}]
    tagged_booking = _booking_item(
        "evt-tagged", thread_id="thread-2", attendees=[{"email": "sender@example.com"}]
    )
    untagged_booking = _booking_item(
        "evt-untagged", attendees=[{"email": "sender@example.com"}], tagged=False
    )
    service.events.return_value.list.return_value.execute.return_value = {
        "items": [hold_item, tagged_booking, untagged_booking]
    }

    booking = find_booking_by_attendee(service, "sender@example.com", now)

    assert booking is not None
    assert booking.id == "evt-untagged"


def test_find_booking_by_attendee_ignores_non_confirmed_events():
    service = _service()
    now = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    service.events.return_value.list.return_value.execute.return_value = {
        "items": [
            _booking_item(
                "evt-1",
                status="cancelled",
                attendees=[{"email": "sender@example.com"}],
                tagged=False,
            )
        ]
    }

    assert find_booking_by_attendee(service, "sender@example.com", now) is None


def test_cancel_booking_deletes_event():
    service = _service()

    cancel_booking(service, "evt-1")

    service.events.return_value.delete.assert_called_once_with(
        calendarId="primary", eventId="evt-1", sendUpdates="none"
    )


def test_cancel_booking_swallows_404():
    service = _service()
    service.events.return_value.delete.return_value.execute.side_effect = _http_error(
        404
    )

    cancel_booking(service, "evt-1")  # should not raise


def test_reschedule_booking_patches_start_and_end():
    service = _service()
    new_start = datetime(2024, 1, 5, 10, 0, tzinfo=timezone.utc)
    new_end = datetime(2024, 1, 5, 10, 30, tzinfo=timezone.utc)

    reschedule_booking(service, "evt-1", new_start, new_end)

    service.events.return_value.patch.assert_called_once_with(
        calendarId="primary",
        eventId="evt-1",
        body={
            "start": {"dateTime": new_start.isoformat()},
            "end": {"dateTime": new_end.isoformat()},
        },
        sendUpdates="none",
    )
