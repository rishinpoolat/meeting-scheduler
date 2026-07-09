from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from agent import main, process_message, run_cycle
from gcalendar.events import Hold
from gcalendar.slots import SLOT_DURATION, TimeSlot
from gmail.read import Message
from llm.classify import Classification

MESSAGE = Message(
    id="msg-1",
    thread_id="thread-1",
    subject="Meeting request",
    from_address="Jane Doe <jane@example.com>",
    message_id_header="<abc@mail.gmail.com>",
    references_header="",
    snippet="",
)

NOW = datetime(2026, 7, 9, 9, 0, tzinfo=timezone.utc)
TZ_NAME = "UTC"

HOLD = Hold(
    id="hold-1",
    thread_id="thread-1",
    start=datetime(2026, 7, 10, 9, 0, tzinfo=timezone.utc),
    end=datetime(2026, 7, 10, 9, 30, tzinfo=timezone.utc),
    created=datetime(2026, 7, 9, 8, 0, tzinfo=timezone.utc),
)


def _classification(**overrides: object) -> Classification:
    fields: dict[str, object] = {
        "intent": "irrelevant",
        "proposed_time": None,
        "matched_hold": None,
    }
    fields.update(overrides)
    return Classification(**fields)  # type: ignore[arg-type]


class TestProcessMessage:
    def test_always_fetches_thread_scoped_holds_before_classifying(self) -> None:
        gmail_service, cal_service, llm_client = MagicMock(), MagicMock(), MagicMock()
        with (
            patch("agent.list_holds", return_value=[HOLD]) as mock_list_holds,
            patch(
                "agent.classify_email", return_value=_classification()
            ) as mock_classify,
        ):
            process_message(
                gmail_service, cal_service, llm_client, MESSAGE, "body", NOW, TZ_NAME
            )

        mock_list_holds.assert_called_once_with(
            cal_service, thread_id=MESSAGE.thread_id
        )
        mock_classify.assert_called_once_with(llm_client, MESSAGE, "body", NOW, [HOLD])

    def test_irrelevant_intent_is_a_noop(self) -> None:
        gmail_service, cal_service, llm_client = MagicMock(), MagicMock(), MagicMock()
        with (
            patch("agent.list_holds", return_value=[]),
            patch(
                "agent.classify_email",
                return_value=_classification(intent="irrelevant"),
            ),
            patch("agent.book_event") as mock_book,
            patch("agent.create_hold") as mock_hold,
            patch("agent.confirm_hold") as mock_confirm,
            patch("agent.create_draft_reply") as mock_draft_reply,
            patch("agent.draft_booking_confirmation") as mock_draft_confirm,
            patch("agent.draft_time_unavailable") as mock_draft_unavailable,
            patch("agent.draft_slot_offer") as mock_draft_offer,
            patch("agent.draft_slot_confirmed") as mock_draft_slot_confirmed,
        ):
            process_message(
                gmail_service, cal_service, llm_client, MESSAGE, "body", NOW, TZ_NAME
            )

        mock_book.assert_not_called()
        mock_hold.assert_not_called()
        mock_confirm.assert_not_called()
        mock_draft_reply.assert_not_called()
        mock_draft_confirm.assert_not_called()
        mock_draft_unavailable.assert_not_called()
        mock_draft_offer.assert_not_called()
        mock_draft_slot_confirmed.assert_not_called()

    def test_propose_time_free_slot_books_and_confirms(self) -> None:
        gmail_service, cal_service, llm_client = MagicMock(), MagicMock(), MagicMock()
        proposed_time = datetime(2026, 7, 10, 14, 0, tzinfo=timezone.utc)
        end = proposed_time + SLOT_DURATION
        with (
            patch("agent.list_holds", return_value=[]),
            patch(
                "agent.classify_email",
                return_value=_classification(
                    intent="propose_time", proposed_time=proposed_time
                ),
            ),
            patch("agent.is_slot_free", return_value=True) as mock_is_free,
            patch("agent.book_event") as mock_book,
            patch(
                "agent.draft_booking_confirmation", return_value="confirmed!"
            ) as mock_draft_confirm,
            patch("agent.draft_time_unavailable") as mock_draft_unavailable,
            patch("agent.create_draft_reply") as mock_draft_reply,
        ):
            process_message(
                gmail_service, cal_service, llm_client, MESSAGE, "body", NOW, TZ_NAME
            )

        mock_is_free.assert_called_once_with(cal_service, proposed_time, end, TZ_NAME)
        mock_book.assert_called_once_with(
            cal_service,
            "Meeting: Jane Doe <jane@example.com> — Meeting request",
            proposed_time,
            end,
            "jane@example.com",
        )
        mock_draft_confirm.assert_called_once_with(
            llm_client, MESSAGE, proposed_time, end
        )
        mock_draft_unavailable.assert_not_called()
        mock_draft_reply.assert_called_once_with(gmail_service, MESSAGE, "confirmed!")

    def test_propose_time_busy_slot_skips_booking(self) -> None:
        gmail_service, cal_service, llm_client = MagicMock(), MagicMock(), MagicMock()
        proposed_time = datetime(2026, 7, 10, 14, 0, tzinfo=timezone.utc)
        end = proposed_time + SLOT_DURATION
        with (
            patch("agent.list_holds", return_value=[]),
            patch(
                "agent.classify_email",
                return_value=_classification(
                    intent="propose_time", proposed_time=proposed_time
                ),
            ),
            patch("agent.is_slot_free", return_value=False),
            patch("agent.book_event") as mock_book,
            patch("agent.draft_booking_confirmation") as mock_draft_confirm,
            patch(
                "agent.draft_time_unavailable", return_value="sorry!"
            ) as mock_draft_unavailable,
            patch("agent.create_draft_reply") as mock_draft_reply,
        ):
            process_message(
                gmail_service, cal_service, llm_client, MESSAGE, "body", NOW, TZ_NAME
            )

        mock_book.assert_not_called()
        mock_draft_confirm.assert_not_called()
        mock_draft_unavailable.assert_called_once_with(
            llm_client, MESSAGE, proposed_time, end
        )
        mock_draft_reply.assert_called_once_with(gmail_service, MESSAGE, "sorry!")

    def test_propose_time_in_the_past_is_treated_as_unavailable(self) -> None:
        gmail_service, cal_service, llm_client = MagicMock(), MagicMock(), MagicMock()
        proposed_time = NOW - timedelta(hours=1)
        end = proposed_time + SLOT_DURATION
        with (
            patch("agent.list_holds", return_value=[]),
            patch(
                "agent.classify_email",
                return_value=_classification(
                    intent="propose_time", proposed_time=proposed_time
                ),
            ),
            patch("agent.is_slot_free") as mock_is_free,
            patch("agent.book_event") as mock_book,
            patch("agent.draft_booking_confirmation") as mock_draft_confirm,
            patch(
                "agent.draft_time_unavailable", return_value="that's in the past!"
            ) as mock_draft_unavailable,
            patch("agent.create_draft_reply") as mock_draft_reply,
        ):
            process_message(
                gmail_service, cal_service, llm_client, MESSAGE, "body", NOW, TZ_NAME
            )

        mock_is_free.assert_not_called()
        mock_book.assert_not_called()
        mock_draft_confirm.assert_not_called()
        mock_draft_unavailable.assert_called_once_with(
            llm_client, MESSAGE, proposed_time, end
        )
        mock_draft_reply.assert_called_once_with(
            gmail_service, MESSAGE, "that's in the past!"
        )

    def test_propose_time_extracts_bare_email_for_attendee(self) -> None:
        gmail_service, cal_service, llm_client = MagicMock(), MagicMock(), MagicMock()
        proposed_time = datetime(2026, 7, 10, 14, 0, tzinfo=timezone.utc)
        with (
            patch("agent.list_holds", return_value=[]),
            patch(
                "agent.classify_email",
                return_value=_classification(
                    intent="propose_time", proposed_time=proposed_time
                ),
            ),
            patch("agent.is_slot_free", return_value=True),
            patch("agent.book_event") as mock_book,
            patch("agent.draft_booking_confirmation", return_value="x"),
            patch("agent.create_draft_reply"),
        ):
            process_message(
                gmail_service, cal_service, llm_client, MESSAGE, "body", NOW, TZ_NAME
            )

        assert mock_book.call_args.args[4] == "jane@example.com"

    def test_ask_availability_creates_one_hold_per_slot_tagged_with_thread_id(
        self,
    ) -> None:
        gmail_service, cal_service, llm_client = MagicMock(), MagicMock(), MagicMock()
        slots = [
            TimeSlot(
                start=datetime(2026, 7, 10, 9, 0, tzinfo=timezone.utc),
                end=datetime(2026, 7, 10, 9, 30, tzinfo=timezone.utc),
            ),
            TimeSlot(
                start=datetime(2026, 7, 10, 13, 0, tzinfo=timezone.utc),
                end=datetime(2026, 7, 10, 13, 30, tzinfo=timezone.utc),
            ),
        ]
        with (
            patch("agent.list_holds", return_value=[]),
            patch(
                "agent.classify_email",
                return_value=_classification(intent="ask_availability"),
            ),
            patch("agent.find_open_slots", return_value=slots) as mock_find_slots,
            patch("agent.create_hold") as mock_create_hold,
            patch(
                "agent.draft_slot_offer", return_value="here are some times"
            ) as mock_draft_offer,
            patch("agent.create_draft_reply") as mock_draft_reply,
        ):
            process_message(
                gmail_service, cal_service, llm_client, MESSAGE, "body", NOW, TZ_NAME
            )

        mock_find_slots.assert_called_once_with(cal_service, now=NOW)
        assert mock_create_hold.call_count == 2
        for call, slot in zip(mock_create_hold.call_args_list, slots):
            assert call.args == (
                cal_service,
                "Meeting: Jane Doe <jane@example.com> — Meeting request",
                slot.start,
                slot.end,
                "jane@example.com",
                MESSAGE.thread_id,
            )
        mock_draft_offer.assert_called_once_with(llm_client, MESSAGE, slots)
        mock_draft_reply.assert_called_once_with(
            gmail_service, MESSAGE, "here are some times"
        )

    def test_ask_availability_with_no_open_slots_creates_no_holds_but_still_drafts(
        self,
    ) -> None:
        gmail_service, cal_service, llm_client = MagicMock(), MagicMock(), MagicMock()
        with (
            patch("agent.list_holds", return_value=[]),
            patch(
                "agent.classify_email",
                return_value=_classification(intent="ask_availability"),
            ),
            patch("agent.find_open_slots", return_value=[]),
            patch("agent.create_hold") as mock_create_hold,
            patch(
                "agent.draft_slot_offer", return_value="nothing open"
            ) as mock_draft_offer,
            patch("agent.create_draft_reply") as mock_draft_reply,
        ):
            process_message(
                gmail_service, cal_service, llm_client, MESSAGE, "body", NOW, TZ_NAME
            )

        mock_create_hold.assert_not_called()
        mock_draft_offer.assert_called_once_with(llm_client, MESSAGE, [])
        mock_draft_reply.assert_called_once_with(gmail_service, MESSAGE, "nothing open")

    def test_accept_slot_confirms_hold_with_correct_arg_order(self) -> None:
        gmail_service, cal_service, llm_client = MagicMock(), MagicMock(), MagicMock()
        with (
            patch("agent.list_holds", return_value=[HOLD]),
            patch(
                "agent.classify_email",
                return_value=_classification(intent="accept_slot", matched_hold=HOLD),
            ),
            patch("agent.confirm_hold") as mock_confirm,
            patch(
                "agent.draft_slot_confirmed", return_value="booked!"
            ) as mock_draft_confirmed,
            patch("agent.create_draft_reply") as mock_draft_reply,
        ):
            process_message(
                gmail_service, cal_service, llm_client, MESSAGE, "body", NOW, TZ_NAME
            )

        mock_confirm.assert_called_once_with(cal_service, MESSAGE.thread_id, HOLD.id)
        mock_draft_confirmed.assert_called_once_with(llm_client, MESSAGE, HOLD)
        mock_draft_reply.assert_called_once_with(gmail_service, MESSAGE, "booked!")


class TestRunCycle:
    def test_processes_every_unread_message_id(self) -> None:
        gmail_service, cal_service, llm_client = MagicMock(), MagicMock(), MagicMock()
        message_1 = Message(
            id="m1",
            thread_id="t1",
            subject="A",
            from_address="a@example.com",
            message_id_header="<a>",
            references_header="",
            snippet="",
        )
        message_2 = Message(
            id="m2",
            thread_id="t2",
            subject="B",
            from_address="b@example.com",
            message_id_header="<b>",
            references_header="",
            snippet="",
        )
        with (
            patch("agent.expire_stale_holds") as mock_sweep,
            patch("agent.get_calendar_timezone", return_value=TZ_NAME),
            patch("agent.list_unread_message_ids", return_value=["m1", "m2"]),
            patch(
                "agent.get_message", side_effect=[message_1, message_2]
            ) as mock_get_message,
            patch(
                "agent.get_message_body", side_effect=["body1", "body2"]
            ) as mock_get_body,
            patch("agent.process_message") as mock_process,
            patch("agent.mark_as_read") as mock_mark_read,
        ):
            run_cycle(gmail_service, cal_service, llm_client)

        mock_sweep.assert_called_once_with(cal_service)
        assert mock_get_message.call_args_list == [
            ((gmail_service, "m1"),),
            ((gmail_service, "m2"),),
        ]
        assert mock_get_body.call_args_list == [
            ((gmail_service, "m1"),),
            ((gmail_service, "m2"),),
        ]
        assert mock_process.call_count == 2
        first_call, second_call = mock_process.call_args_list
        assert first_call.args[:5] == (
            gmail_service,
            cal_service,
            llm_client,
            message_1,
            "body1",
        )
        assert second_call.args[:5] == (
            gmail_service,
            cal_service,
            llm_client,
            message_2,
            "body2",
        )
        # same now/tz_name reused across both calls
        assert first_call.args[5:] == second_call.args[5:]
        assert mock_mark_read.call_args_list == [
            ((gmail_service, "m1"),),
            ((gmail_service, "m2"),),
        ]

    def test_computes_now_from_calendar_timezone(self) -> None:
        gmail_service, cal_service, llm_client = MagicMock(), MagicMock(), MagicMock()
        fixed_now = datetime(2026, 7, 9, 12, 0, tzinfo=ZoneInfo("America/New_York"))
        with (
            patch("agent.expire_stale_holds"),
            patch("agent.get_calendar_timezone", return_value="America/New_York"),
            patch("agent.list_unread_message_ids", return_value=["m1"]),
            patch(
                "agent.get_message",
                return_value=MESSAGE,
            ),
            patch("agent.get_message_body", return_value="body"),
            patch("agent.datetime") as mock_datetime,
            patch("agent.process_message") as mock_process,
            patch("agent.mark_as_read"),
        ):
            mock_datetime.now.return_value = fixed_now
            run_cycle(gmail_service, cal_service, llm_client)

        mock_datetime.now.assert_called_once_with(ZoneInfo("America/New_York"))
        assert mock_process.call_args.args[5] == fixed_now
        assert mock_process.call_args.args[6] == "America/New_York"

    def test_with_no_unread_messages_does_nothing(self) -> None:
        gmail_service, cal_service, llm_client = MagicMock(), MagicMock(), MagicMock()
        with (
            patch("agent.expire_stale_holds"),
            patch("agent.get_calendar_timezone", return_value=TZ_NAME) as mock_tz,
            patch("agent.list_unread_message_ids", return_value=[]),
            patch("agent.process_message") as mock_process,
            patch("agent.mark_as_read") as mock_mark_read,
        ):
            run_cycle(gmail_service, cal_service, llm_client)

        mock_tz.assert_called_once_with(cal_service)
        mock_process.assert_not_called()
        mock_mark_read.assert_not_called()

    def test_sweeps_stale_holds_before_listing_unread_messages(self) -> None:
        gmail_service, cal_service, llm_client = MagicMock(), MagicMock(), MagicMock()
        call_order: list[str] = []

        def _record_sweep(*_a: object, **_k: object) -> None:
            call_order.append("sweep")

        def _record_list(*_a: object, **_k: object) -> list[str]:
            call_order.append("list")
            return []

        with (
            patch("agent.expire_stale_holds", side_effect=_record_sweep),
            patch("agent.get_calendar_timezone", return_value=TZ_NAME),
            patch("agent.list_unread_message_ids", side_effect=_record_list),
        ):
            run_cycle(gmail_service, cal_service, llm_client)

        assert call_order == ["sweep", "list"]

    def test_sweep_failure_is_not_caught_and_propagates(self) -> None:
        gmail_service, cal_service, llm_client = MagicMock(), MagicMock(), MagicMock()
        with (
            patch("agent.expire_stale_holds", side_effect=Exception("sweep boom")),
            patch("agent.get_calendar_timezone", return_value=TZ_NAME),
            patch("agent.list_unread_message_ids") as mock_list,
        ):
            with pytest.raises(Exception, match="sweep boom"):
                run_cycle(gmail_service, cal_service, llm_client)

        mock_list.assert_not_called()

    def test_marks_message_read_only_after_successful_processing(self) -> None:
        gmail_service, cal_service, llm_client = MagicMock(), MagicMock(), MagicMock()
        with (
            patch("agent.expire_stale_holds"),
            patch("agent.get_calendar_timezone", return_value=TZ_NAME),
            patch("agent.list_unread_message_ids", return_value=["m1"]),
            patch("agent.get_message", return_value=MESSAGE),
            patch("agent.get_message_body", return_value="body"),
            patch("agent.process_message") as mock_process,
            patch("agent.mark_as_read") as mock_mark_read,
        ):
            run_cycle(gmail_service, cal_service, llm_client)

        mock_process.assert_called_once()
        mock_mark_read.assert_called_once_with(gmail_service, "m1")

    def test_process_message_failure_is_isolated_and_message_left_unread(
        self,
    ) -> None:
        gmail_service, cal_service, llm_client = MagicMock(), MagicMock(), MagicMock()
        with (
            patch("agent.expire_stale_holds"),
            patch("agent.get_calendar_timezone", return_value=TZ_NAME),
            patch("agent.list_unread_message_ids", return_value=["m1", "m2"]),
            patch("agent.get_message", return_value=MESSAGE),
            patch("agent.get_message_body", return_value="body"),
            patch(
                "agent.process_message", side_effect=[Exception("boom"), None]
            ) as mock_process,
            patch("agent.mark_as_read") as mock_mark_read,
            patch("agent.logger") as mock_logger,
        ):
            run_cycle(gmail_service, cal_service, llm_client)

        assert mock_process.call_count == 2
        mock_mark_read.assert_called_once_with(gmail_service, "m2")
        mock_logger.exception.assert_called_once()
        assert mock_logger.exception.call_args.args[1] == "m1"

    def test_message_fetch_failure_is_isolated_like_a_processing_failure(
        self,
    ) -> None:
        gmail_service, cal_service, llm_client = MagicMock(), MagicMock(), MagicMock()
        with (
            patch("agent.expire_stale_holds"),
            patch("agent.get_calendar_timezone", return_value=TZ_NAME),
            patch("agent.list_unread_message_ids", return_value=["m1", "m2"]),
            patch(
                "agent.get_message", side_effect=[Exception("fetch failed"), MESSAGE]
            ),
            patch("agent.get_message_body", return_value="body"),
            patch("agent.process_message") as mock_process,
            patch("agent.mark_as_read") as mock_mark_read,
        ):
            run_cycle(gmail_service, cal_service, llm_client)

        mock_process.assert_called_once()
        mock_mark_read.assert_called_once_with(gmail_service, "m2")

    def test_mark_as_read_failure_does_not_prevent_processing_next_message(
        self,
    ) -> None:
        gmail_service, cal_service, llm_client = MagicMock(), MagicMock(), MagicMock()
        with (
            patch("agent.expire_stale_holds"),
            patch("agent.get_calendar_timezone", return_value=TZ_NAME),
            patch("agent.list_unread_message_ids", return_value=["m1", "m2"]),
            patch("agent.get_message", return_value=MESSAGE),
            patch("agent.get_message_body", return_value="body"),
            patch("agent.process_message") as mock_process,
            patch(
                "agent.mark_as_read", side_effect=[Exception("mark failed"), None]
            ) as mock_mark_read,
        ):
            run_cycle(gmail_service, cal_service, llm_client)

        assert mock_process.call_count == 2
        assert mock_mark_read.call_count == 2

    def test_mark_as_read_failure_is_logged_distinctly_from_a_processing_failure(
        self,
    ) -> None:
        gmail_service, cal_service, llm_client = MagicMock(), MagicMock(), MagicMock()
        with (
            patch("agent.expire_stale_holds"),
            patch("agent.get_calendar_timezone", return_value=TZ_NAME),
            patch("agent.list_unread_message_ids", return_value=["m1"]),
            patch("agent.get_message", return_value=MESSAGE),
            patch("agent.get_message_body", return_value="body"),
            patch("agent.process_message"),
            patch("agent.mark_as_read", side_effect=Exception("mark failed")),
            patch("agent.logger") as mock_logger,
        ):
            run_cycle(gmail_service, cal_service, llm_client)

        mock_logger.exception.assert_called_once()
        log_message = mock_logger.exception.call_args.args[0]
        assert "may be reprocessed" in log_message
        assert "leaving unread for retry" not in log_message


def test_main_wires_real_services_into_run_cycle() -> None:
    gmail_service, cal_service, llm_client = MagicMock(), MagicMock(), MagicMock()
    with (
        patch("agent.get_gmail_service", return_value=gmail_service),
        patch("agent.get_calendar_service", return_value=cal_service),
        patch("agent.get_llm_client", return_value=llm_client),
        patch("agent.run_cycle") as mock_run_cycle,
    ):
        main()

    mock_run_cycle.assert_called_once_with(gmail_service, cal_service, llm_client)
