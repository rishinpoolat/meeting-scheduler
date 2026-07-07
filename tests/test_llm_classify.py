from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from config import CLAUDE_MODEL
from gcalendar.events import Hold
from gmail.read import Message
from llm.classify import (
    CLASSIFY_TOOL,
    CLASSIFY_TOOL_NAME,
    Classification,
    classify_email,
)

MESSAGE = Message(
    id="msg-1",
    thread_id="thread-1",
    subject="Meeting request",
    from_address="Jane <jane@example.com>",
    message_id_header="<abc@mail.gmail.com>",
    references_header="",
    snippet="",
)

NOW = datetime(2026, 7, 7, 9, 0, tzinfo=timezone.utc)


def _client_with_tool_response(tool_input):
    block = MagicMock()
    block.type = "tool_use"
    block.input = tool_input
    response = MagicMock()
    response.content = [block]
    client = MagicMock()
    client.messages.create.return_value = response
    return client


def _client_with_no_tool_use():
    block = MagicMock()
    block.type = "text"
    response = MagicMock()
    response.content = [block]
    client = MagicMock()
    client.messages.create.return_value = response
    return client


def test_classify_email_propose_time_parses_datetime():
    proposed = "2026-07-09T14:00:00+00:00"
    client = _client_with_tool_response(
        {
            "intent": "propose_time",
            "proposed_time": proposed,
            "accepted_slot_index": None,
        }
    )

    result = classify_email(client, MESSAGE, "Let's meet Thursday at 2pm", NOW, [])

    assert result == Classification(
        intent="propose_time",
        proposed_time=datetime.fromisoformat(proposed),
        matched_hold=None,
    )


def test_classify_email_propose_time_parses_z_suffixed_datetime():
    client = _client_with_tool_response(
        {
            "intent": "propose_time",
            "proposed_time": "2026-07-09T14:00:00Z",
            "accepted_slot_index": None,
        }
    )

    result = classify_email(client, MESSAGE, "Let's meet Thursday at 2pm UTC", NOW, [])

    assert result == Classification(
        intent="propose_time",
        proposed_time=datetime.fromisoformat("2026-07-09T14:00:00+00:00"),
        matched_hold=None,
    )


def test_classify_email_ask_availability():
    client = _client_with_tool_response(
        {
            "intent": "ask_availability",
            "proposed_time": None,
            "accepted_slot_index": None,
        }
    )

    result = classify_email(client, MESSAGE, "When are you free?", NOW, [])

    assert result == Classification(
        intent="ask_availability", proposed_time=None, matched_hold=None
    )


def test_classify_email_accept_slot_maps_index_to_hold():
    holds = [
        Hold(id="hold-1", thread_id="thread-1", start=NOW, end=NOW, created=NOW),
        Hold(id="hold-2", thread_id="thread-1", start=NOW, end=NOW, created=NOW),
    ]
    client = _client_with_tool_response(
        {"intent": "accept_slot", "proposed_time": None, "accepted_slot_index": 2}
    )

    result = classify_email(client, MESSAGE, "Option 2 works!", NOW, holds)

    assert result.intent == "accept_slot"
    assert result.matched_hold is holds[1]


def test_classify_email_irrelevant():
    client = _client_with_tool_response(
        {"intent": "irrelevant", "proposed_time": None, "accepted_slot_index": None}
    )

    result = classify_email(client, MESSAGE, "50% off everything!", NOW, [])

    assert result == Classification(
        intent="irrelevant", proposed_time=None, matched_hold=None
    )


def test_classify_email_downgrades_out_of_range_slot_index_to_irrelevant():
    holds = [Hold(id="hold-1", thread_id="thread-1", start=NOW, end=NOW, created=NOW)]
    client = _client_with_tool_response(
        {"intent": "accept_slot", "proposed_time": None, "accepted_slot_index": 5}
    )

    result = classify_email(client, MESSAGE, "Sounds good", NOW, holds)

    assert result == Classification(
        intent="irrelevant", proposed_time=None, matched_hold=None
    )


def test_classify_email_downgrades_unparseable_proposed_time_to_irrelevant():
    client = _client_with_tool_response(
        {
            "intent": "propose_time",
            "proposed_time": "not-a-date",
            "accepted_slot_index": None,
        }
    )

    result = classify_email(client, MESSAGE, "Let's meet soon", NOW, [])

    assert result == Classification(
        intent="irrelevant", proposed_time=None, matched_hold=None
    )


def test_classify_email_downgrades_naive_proposed_time_to_irrelevant():
    client = _client_with_tool_response(
        {
            "intent": "propose_time",
            "proposed_time": "2026-07-09T14:00:00",
            "accepted_slot_index": None,
        }
    )

    result = classify_email(client, MESSAGE, "Let's meet Thursday at 2pm", NOW, [])

    assert result == Classification(
        intent="irrelevant", proposed_time=None, matched_hold=None
    )


def test_classify_email_raises_value_error_when_no_tool_use_block_returned():
    client = _client_with_no_tool_use()

    with pytest.raises(ValueError):
        classify_email(client, MESSAGE, "body", NOW, [])


def test_classify_email_raises_value_error_for_naive_now():
    client = _client_with_tool_response(
        {"intent": "irrelevant", "proposed_time": None, "accepted_slot_index": None}
    )
    naive_now = datetime(2026, 7, 7, 9, 0)

    with pytest.raises(ValueError):
        classify_email(client, MESSAGE, "body", naive_now, [])


def test_classify_email_prompt_includes_numbered_candidate_holds():
    holds = [
        Hold(
            id="hold-1",
            thread_id="thread-1",
            start=NOW + timedelta(days=1),
            end=NOW + timedelta(days=1, minutes=30),
            created=NOW,
        ),
        Hold(
            id="hold-2",
            thread_id="thread-1",
            start=NOW + timedelta(days=2),
            end=NOW + timedelta(days=2, minutes=30),
            created=NOW,
        ),
    ]
    client = _client_with_tool_response(
        {"intent": "irrelevant", "proposed_time": None, "accepted_slot_index": None}
    )

    classify_email(client, MESSAGE, "body", NOW, holds)

    _, kwargs = client.messages.create.call_args
    prompt = kwargs["messages"][0]["content"]
    assert "Option 1:" in prompt
    assert "Option 2:" in prompt


def test_classify_email_forces_tool_choice_and_model():
    client = _client_with_tool_response(
        {"intent": "irrelevant", "proposed_time": None, "accepted_slot_index": None}
    )

    classify_email(client, MESSAGE, "body", NOW, [])

    _, kwargs = client.messages.create.call_args
    assert kwargs["model"] == CLAUDE_MODEL
    assert kwargs["tool_choice"] == {"type": "tool", "name": CLASSIFY_TOOL_NAME}
    assert kwargs["tools"] == [CLASSIFY_TOOL]
