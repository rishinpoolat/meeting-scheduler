"""Entry point: orchestrates one Gmail-polling cycle end to end."""

import logging
from datetime import datetime
from email.utils import parseaddr
from typing import Any
from zoneinfo import ZoneInfo

from gcalendar.client import get_service as get_calendar_service
from gcalendar.events import (
    Hold,
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
from gcalendar.freebusy import get_calendar_timezone, is_slot_free
from gcalendar.slots import SLOT_DURATION, find_open_slots
from gmail.client import get_service as get_gmail_service
from gmail.draft import create_draft_reply
from gmail.profile import get_display_name
from gmail.read import (
    Message,
    get_message,
    get_message_body,
    list_unread_message_ids,
    mark_as_read,
)
from llm.classify import classify_email
from llm.client import get_client as get_llm_client
from llm.draft import (
    draft_booking_confirmation,
    draft_booking_not_found,
    draft_cancellation_confirmation,
    draft_reschedule_confirmation,
    draft_reschedule_unavailable,
    draft_slot_confirmed,
    draft_slot_offer,
    draft_time_unavailable,
)

logger = logging.getLogger(__name__)

# Unread messages one run considers: at most UNREAD_BATCH_SIZE, and only
# those from the last UNREAD_WINDOW_DAYS days - both apply together. The
# count cap exists to stay well under Gemini's free-tier rate limit even
# if the date window catches a burst of unread mail.
# gmail.read.list_unread_message_ids's own defaults stay wider (no date
# filter, higher count) for general-purpose use e.g. scripts/check_gmail.py.
UNREAD_BATCH_SIZE = 5
UNREAD_WINDOW_DAYS = 2


def main() -> None:
    """Run one polling cycle against the real Gmail/Calendar/Gemini APIs."""
    run_cycle(get_gmail_service(), get_calendar_service(), get_llm_client())


def run_cycle(gmail_service: Any, cal_service: Any, llm_client: Any) -> None:
    """Sweep stale holds, then process and mark read every unread message."""
    expire_stale_holds(cal_service)
    tz_name = get_calendar_timezone(cal_service)
    now = datetime.now(ZoneInfo(tz_name))
    your_name = get_display_name(gmail_service)
    for message_id in list_unread_message_ids(
        gmail_service, max_results=UNREAD_BATCH_SIZE, newer_than_days=UNREAD_WINDOW_DAYS
    ):
        try:
            message = get_message(gmail_service, message_id)
            body = get_message_body(gmail_service, message_id)
            process_message(
                gmail_service,
                cal_service,
                llm_client,
                message,
                body,
                now,
                tz_name,
                your_name,
            )
        except Exception:
            logger.exception(
                "Failed to process message id=%s; leaving unread for retry",
                message_id,
            )
            continue
        try:
            mark_as_read(gmail_service, message_id)
        except Exception:
            logger.exception(
                "Processed message id=%s but failed to mark it read; it may be "
                "reprocessed next run",
                message_id,
            )


def process_message(
    gmail_service: Any,
    cal_service: Any,
    llm_client: Any,
    message: Message,
    body: str,
    now: datetime,
    tz_name: str,
    your_name: str,
) -> None:
    """Classify one already-fetched email and act on it."""
    candidate_holds = list_holds(cal_service, thread_id=message.thread_id)
    classification = classify_email(llm_client, message, body, now, candidate_holds)

    if classification.intent == "propose_time":
        assert classification.proposed_time is not None
        _handle_propose_time(
            gmail_service,
            cal_service,
            llm_client,
            message,
            classification.proposed_time,
            now,
            tz_name,
            your_name,
        )
    elif classification.intent == "ask_availability":
        _handle_ask_availability(
            gmail_service,
            cal_service,
            llm_client,
            message,
            now,
            classification.earliest_offer_time,
            your_name,
        )
    elif classification.intent == "accept_slot":
        assert classification.matched_hold is not None
        _handle_accept_slot(
            gmail_service,
            cal_service,
            llm_client,
            message,
            classification.matched_hold,
            your_name,
        )
    elif classification.intent == "cancel_or_reschedule":
        _handle_cancel_or_reschedule(
            gmail_service,
            cal_service,
            llm_client,
            message,
            classification.new_proposed_time,
            now,
            tz_name,
            your_name,
        )
    # "irrelevant" -> no draft, no calendar write.


def _handle_propose_time(
    gmail_service: Any,
    cal_service: Any,
    llm_client: Any,
    message: Message,
    proposed_time: datetime,
    now: datetime,
    tz_name: str,
    your_name: str,
) -> None:
    end = proposed_time + SLOT_DURATION
    if proposed_time > now and is_slot_free(cal_service, proposed_time, end, tz_name):
        book_event(
            cal_service,
            _event_summary(message),
            proposed_time,
            end,
            _sender_email(message),
            message.thread_id,
        )
        reply_body = draft_booking_confirmation(
            llm_client, message, proposed_time, end, your_name
        )
    else:
        reply_body = draft_time_unavailable(
            llm_client, message, proposed_time, end, your_name
        )
    create_draft_reply(gmail_service, message, reply_body)


def _handle_ask_availability(
    gmail_service: Any,
    cal_service: Any,
    llm_client: Any,
    message: Message,
    now: datetime,
    earliest_offer_time: datetime | None,
    your_name: str,
) -> None:
    slots = find_open_slots(cal_service, now=now, earliest=earliest_offer_time)
    attendee_email = _sender_email(message)
    for slot in slots:
        create_hold(
            cal_service,
            _event_summary(message),
            slot.start,
            slot.end,
            attendee_email,
            message.thread_id,
        )
    reply_body = draft_slot_offer(llm_client, message, slots, your_name)
    create_draft_reply(gmail_service, message, reply_body)


def _handle_accept_slot(
    gmail_service: Any,
    cal_service: Any,
    llm_client: Any,
    message: Message,
    hold: Hold,
    your_name: str,
) -> None:
    confirm_hold(cal_service, message.thread_id, hold.id)
    reply_body = draft_slot_confirmed(llm_client, message, hold, your_name)
    create_draft_reply(gmail_service, message, reply_body)


def _handle_cancel_or_reschedule(
    gmail_service: Any,
    cal_service: Any,
    llm_client: Any,
    message: Message,
    new_time: datetime | None,
    now: datetime,
    tz_name: str,
    your_name: str,
) -> None:
    booking = find_booking_by_thread(cal_service, message.thread_id)
    if booking is None:
        booking = find_booking_by_attendee(cal_service, _sender_email(message), now)
    if booking is None:
        reply_body = draft_booking_not_found(llm_client, message, your_name)
        create_draft_reply(gmail_service, message, reply_body)
        return

    if new_time is None:
        cancel_booking(cal_service, booking.id)
        reply_body = draft_cancellation_confirmation(
            llm_client, message, booking.start, booking.end, your_name
        )
    else:
        new_end = new_time + (booking.end - booking.start)
        if new_time > now and is_slot_free(cal_service, new_time, new_end, tz_name):
            reschedule_booking(cal_service, booking.id, new_time, new_end)
            reply_body = draft_reschedule_confirmation(
                llm_client, message, new_time, new_end, your_name
            )
        else:
            reply_body = draft_reschedule_unavailable(
                llm_client, message, new_time, new_end, your_name
            )
    create_draft_reply(gmail_service, message, reply_body)


def _sender_email(message: Message) -> str:
    """Extract a bare address from a `From` header (Calendar's attendees.email
    field rejects "Name <addr>" display-name formatting)."""
    _, addr = parseaddr(message.from_address)
    return addr or message.from_address


def _event_summary(message: Message) -> str:
    return f"Meeting: {message.from_address} — {message.subject}"


if __name__ == "__main__":
    main()
