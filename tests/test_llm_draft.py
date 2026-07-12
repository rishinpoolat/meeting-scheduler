from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from config import GEMINI_MODEL
from gcalendar.events import Hold
from gcalendar.slots import TimeSlot
from gmail.read import Message
from llm.draft import (
    _format_date,
    _format_range,
    _format_time,
    _greeting_name,
    draft_booking_confirmation,
    draft_slot_confirmed,
    draft_slot_offer,
    draft_time_unavailable,
)

MESSAGE = Message(
    id="msg-1",
    thread_id="thread-1",
    subject="Meeting request",
    from_address="Jane Doe <jane@example.com>",
    message_id_header="<abc@mail.gmail.com>",
    references_header="",
    snippet="",
)

START = datetime(2026, 7, 9, 9, 0, tzinfo=timezone.utc)
END = datetime(2026, 7, 9, 9, 30, tzinfo=timezone.utc)
HOLD = Hold(id="hold-1", thread_id="thread-1", start=START, end=END, created=START)
YOUR_NAME = "Mohammed Rishin Poolat"

DRAFT_CASES = [
    (draft_booking_confirmation, (MESSAGE, START, END, YOUR_NAME)),
    (draft_time_unavailable, (MESSAGE, START, END, YOUR_NAME)),
    (draft_slot_offer, (MESSAGE, [TimeSlot(start=START, end=END)], YOUR_NAME)),
    (draft_slot_confirmed, (MESSAGE, HOLD, YOUR_NAME)),
]

PLACEHOLDER_DRAFT_CASES = [
    (draft_booking_confirmation, (MESSAGE, START, END, YOUR_NAME), "[[MEETING_TIME]]"),
    (draft_time_unavailable, (MESSAGE, START, END, YOUR_NAME), "[[MEETING_TIME]]"),
    (draft_slot_confirmed, (MESSAGE, HOLD, YOUR_NAME), "[[MEETING_TIME]]"),
    (
        draft_slot_offer,
        (MESSAGE, [TimeSlot(start=START, end=END)], YOUR_NAME),
        "[[SLOT_LIST]]",
    ),
]


def _placeholder_for(draft_fn):
    return "[[SLOT_LIST]]" if draft_fn is draft_slot_offer else "[[MEETING_TIME]]"


def _client_with_text(text):
    response = MagicMock()
    response.text = text
    client = MagicMock()
    client.models.generate_content.return_value = response
    return client


def _client_with_empty_text():
    # The real SDK's .text returns None (not "") when there are no text
    # parts, e.g. an empty/safety-blocked response - match that here.
    response = MagicMock()
    response.text = None
    client = MagicMock()
    client.models.generate_content.return_value = response
    return client


def _prompt(client):
    _, kwargs = client.models.generate_content.call_args
    return kwargs["contents"]


def test_format_time_strips_leading_zero_and_handles_noon_midnight():
    cases = [
        (0, "12:00 AM"),
        (9, "9:00 AM"),
        (12, "12:00 PM"),
        (13, "1:00 PM"),
        (23, "11:00 PM"),
    ]
    for hour, expected in cases:
        dt = datetime(2026, 7, 9, hour, 0, tzinfo=timezone.utc)
        assert _format_time(dt) == expected


def test_format_date_has_no_leading_zero_on_day():
    assert _format_date(datetime(2026, 7, 9, 9, 0, tzinfo=timezone.utc)) == (
        "Thursday, July 9, 2026"
    )


def test_format_range_produces_unambiguous_12_hour_phrase():
    # Pins the exact real-world case that was previously corrupted
    # non-deterministically by Gemini's free-text reformatting.
    start = datetime(2026, 7, 13, 13, 0, tzinfo=timezone.utc)
    end = datetime(2026, 7, 13, 13, 30, tzinfo=timezone.utc)

    assert _format_range(start, end) == "Monday, July 13, 2026 from 1:00 PM to 1:30 PM"


def test_draft_booking_confirmation_replaces_placeholder_with_formatted_time():
    client = _client_with_text("Sounds great, see you [[MEETING_TIME]]!")

    result = draft_booking_confirmation(client, MESSAGE, START, END, YOUR_NAME)

    assert result == (
        "Sounds great, see you Thursday, July 9, 2026 from 9:00 AM to 9:30 AM!"
    )
    prompt = _prompt(client)
    assert "09:00" not in prompt
    assert "9:00 AM" not in prompt
    assert "[[MEETING_TIME]]" in prompt


def test_draft_time_unavailable_replaces_placeholder_with_formatted_time():
    client = _client_with_text("Sorry, [[MEETING_TIME]] doesn't work.")

    result = draft_time_unavailable(client, MESSAGE, START, END, YOUR_NAME)

    assert result == (
        "Sorry, Thursday, July 9, 2026 from 9:00 AM to 9:30 AM doesn't work."
    )
    prompt = _prompt(client)
    assert "09:00" not in prompt
    assert "[[MEETING_TIME]]" in prompt


def test_draft_slot_confirmed_replaces_placeholder_with_formatted_time():
    client = _client_with_text("Confirmed for [[MEETING_TIME]]!")

    result = draft_slot_confirmed(client, MESSAGE, HOLD, YOUR_NAME)

    assert result == "Confirmed for Thursday, July 9, 2026 from 9:00 AM to 9:30 AM!"
    prompt = _prompt(client)
    assert "09:00" not in prompt
    assert "[[MEETING_TIME]]" in prompt


def test_draft_slot_offer_replaces_placeholder_with_bulleted_slot_list():
    client = _client_with_text("Here are some times:\n[[SLOT_LIST]]\nLet me know!")
    slots = [
        TimeSlot(start=START, end=END),
        TimeSlot(start=START.replace(hour=13), end=END.replace(hour=13, minute=30)),
    ]

    result = draft_slot_offer(client, MESSAGE, slots, YOUR_NAME)

    assert (
        "- Thursday, July 9, 2026 from 9:00 AM to 9:30 AM\n"
        "- Thursday, July 9, 2026 from 1:00 PM to 1:30 PM"
    ) in result
    prompt = _prompt(client)
    assert "09:00" not in prompt
    assert "13:00" not in prompt
    assert "[[SLOT_LIST]]" in prompt


def test_draft_slot_offer_with_no_slots_skips_placeholder_and_completes_directly():
    client = _client_with_text("Sorry, nothing is open right now.")

    result = draft_slot_offer(client, MESSAGE, [], YOUR_NAME)

    assert result == "Sorry, nothing is open right now."
    prompt = _prompt(client)
    assert "[[SLOT_LIST]]" not in prompt
    assert "no open times" in prompt.lower()


@pytest.mark.parametrize("draft_fn, args, placeholder", PLACEHOLDER_DRAFT_CASES)
def test_draft_functions_raise_value_error_when_placeholder_missing(
    draft_fn, args, placeholder
):
    # Simulates the observed bug: Gemini writes a plausible-looking reply
    # but never emits the placeholder (e.g. it wrote the time out itself
    # instead of leaving the marker) - must fail loudly, not draft an
    # unverified time.
    client = _client_with_text("A friendly reply with no placeholder at all.")

    with pytest.raises(ValueError):
        draft_fn(client, *args)


@pytest.mark.parametrize("draft_fn, args, placeholder", PLACEHOLDER_DRAFT_CASES)
def test_draft_functions_raise_value_error_when_placeholder_duplicated(
    draft_fn, args, placeholder
):
    # A duplicated placeholder is worse than a missing one if unguarded:
    # str.replace(..., 1) would only fix the first occurrence, leaking a
    # literal placeholder string into the drafted email. Must fail loudly
    # instead of silently shipping a visibly broken draft.
    client = _client_with_text(f"{placeholder} some text {placeholder}")

    with pytest.raises(ValueError):
        draft_fn(client, *args)


@pytest.mark.parametrize("draft_fn, args", DRAFT_CASES)
def test_draft_functions_include_your_name_in_prompt(draft_fn, args):
    client = _client_with_text(f"Reply text {_placeholder_for(draft_fn)}.")

    draft_fn(client, *args)

    prompt = _prompt(client)
    assert YOUR_NAME in prompt


@pytest.mark.parametrize("draft_fn, args", DRAFT_CASES)
def test_draft_functions_instruct_no_subject_line(draft_fn, args):
    client = _client_with_text(f"Reply text {_placeholder_for(draft_fn)}.")

    draft_fn(client, *args)

    prompt = _prompt(client)
    assert "do not include a subject line" in prompt.lower()


@pytest.mark.parametrize("draft_fn, args", DRAFT_CASES)
def test_draft_functions_strip_leading_subject_line_despite_instruction(draft_fn, args):
    placeholder = _placeholder_for(draft_fn)
    client = _client_with_text(
        f"Subject: Re: Meeting Schedule\n\nHi there,\n\nBody {placeholder}."
    )

    result = draft_fn(client, *args)

    assert result.startswith("Hi there,\n\nBody ")
    assert placeholder not in result


@pytest.mark.parametrize("draft_fn, args", DRAFT_CASES)
def test_draft_functions_use_correct_model_and_strip_response_text(draft_fn, args):
    placeholder = _placeholder_for(draft_fn)
    client = _client_with_text(f"  Reply text {placeholder}.  ")

    result = draft_fn(client, *args)

    assert result.startswith("Reply text ")
    assert placeholder not in result
    _, kwargs = client.models.generate_content.call_args
    assert kwargs["model"] == GEMINI_MODEL
    # Locks in the thinking_budget=0 fix - draft.py has no response_schema
    # to detect truncation via a parse failure, so a regression here could
    # silently produce a truncated draft with no error raised.
    assert kwargs["config"].thinking_config.thinking_budget == 0


@pytest.mark.parametrize("draft_fn, args", DRAFT_CASES)
def test_draft_functions_raise_value_error_on_empty_response_content(draft_fn, args):
    client = _client_with_empty_text()

    with pytest.raises(ValueError):
        draft_fn(client, *args)


def test_greeting_name_parses_display_name_and_bare_email():
    assert _greeting_name("Jane Doe <jane@example.com>") == "Jane Doe"
    assert _greeting_name("jane@example.com") == "jane"
