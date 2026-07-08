from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from config import GEMINI_MODEL
from gcalendar.events import Hold
from gcalendar.slots import TimeSlot
from gmail.read import Message
from llm.draft import (
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

DRAFT_CASES = [
    (draft_booking_confirmation, (MESSAGE, START, END)),
    (draft_time_unavailable, (MESSAGE, START, END)),
    (draft_slot_offer, (MESSAGE, [TimeSlot(start=START, end=END)])),
    (draft_slot_confirmed, (MESSAGE, HOLD)),
]


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


def test_draft_booking_confirmation_includes_start_end_in_prompt():
    client = _client_with_text("Sounds great, see you then!")

    result = draft_booking_confirmation(client, MESSAGE, START, END)

    assert result == "Sounds great, see you then!"
    prompt = _prompt(client)
    assert "09:00" in prompt
    assert "09:30" in prompt


def test_draft_time_unavailable_includes_requested_time_in_prompt():
    client = _client_with_text("Sorry, that time doesn't work.")

    draft_time_unavailable(client, MESSAGE, START, END)

    prompt = _prompt(client)
    assert "09:00" in prompt
    assert "09:30" in prompt


def test_draft_slot_offer_includes_all_slots_in_prompt():
    client = _client_with_text("Here are some times.")
    slots = [
        TimeSlot(start=START, end=END),
        TimeSlot(start=START.replace(hour=13), end=END.replace(hour=13, minute=30)),
    ]

    draft_slot_offer(client, MESSAGE, slots)

    prompt = _prompt(client)
    assert "09:00" in prompt
    assert "13:00" in prompt


def test_draft_slot_confirmed_includes_hold_time_in_prompt():
    client = _client_with_text("Confirmed!")

    draft_slot_confirmed(client, MESSAGE, HOLD)

    prompt = _prompt(client)
    assert "09:00" in prompt
    assert "09:30" in prompt


@pytest.mark.parametrize("draft_fn, args", DRAFT_CASES)
def test_draft_functions_use_correct_model_and_strip_response_text(draft_fn, args):
    client = _client_with_text("  Reply text.  ")

    result = draft_fn(client, *args)

    assert result == "Reply text."
    _, kwargs = client.models.generate_content.call_args
    assert kwargs["model"] == GEMINI_MODEL


@pytest.mark.parametrize("draft_fn, args", DRAFT_CASES)
def test_draft_functions_raise_value_error_on_empty_response_content(draft_fn, args):
    client = _client_with_empty_text()

    with pytest.raises(ValueError):
        draft_fn(client, *args)


def test_greeting_name_parses_display_name_and_bare_email():
    assert _greeting_name("Jane Doe <jane@example.com>") == "Jane Doe"
    assert _greeting_name("jane@example.com") == "jane"
