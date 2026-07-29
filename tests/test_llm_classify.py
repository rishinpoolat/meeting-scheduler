from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from config import GEMINI_MODEL
from gcalendar.events import Hold
from gmail.read import Message
from llm.classify import Classification, ClassificationResult, classify_email

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


def _client_with_result(**overrides):
    fields = {
        "intent": "irrelevant",
        "proposed_time": None,
        "earliest_offer_time": None,
        "accepted_slot_index": None,
        "new_proposed_time": None,
    }
    fields.update(overrides)
    response = MagicMock()
    response.parsed = ClassificationResult(**fields)
    client = MagicMock()
    client.models.generate_content.return_value = response
    return client


def _client_with_no_parsed_result(finish_reason="SAFETY"):
    candidate = MagicMock()
    candidate.finish_reason = finish_reason
    response = MagicMock()
    response.parsed = None
    response.candidates = [candidate]
    client = MagicMock()
    client.models.generate_content.return_value = response
    return client


def test_classify_email_propose_time_parses_datetime():
    proposed = "2026-07-09T14:00:00+00:00"
    client = _client_with_result(
        intent="propose_time", proposed_time=proposed, accepted_slot_index=None
    )

    result = classify_email(client, MESSAGE, "Let's meet Thursday at 2pm", NOW, [])

    assert result == Classification(
        intent="propose_time",
        proposed_time=datetime.fromisoformat(proposed),
        matched_hold=None,
        earliest_offer_time=None,
        new_proposed_time=None,
    )


def test_classify_email_propose_time_parses_z_suffixed_datetime():
    client = _client_with_result(
        intent="propose_time",
        proposed_time="2026-07-09T14:00:00Z",
        accepted_slot_index=None,
    )

    result = classify_email(client, MESSAGE, "Let's meet Thursday at 2pm UTC", NOW, [])

    assert result == Classification(
        intent="propose_time",
        proposed_time=datetime.fromisoformat("2026-07-09T14:00:00+00:00"),
        matched_hold=None,
        earliest_offer_time=None,
        new_proposed_time=None,
    )


def test_classify_email_ask_availability():
    client = _client_with_result(intent="ask_availability")

    result = classify_email(client, MESSAGE, "When are you free?", NOW, [])

    assert result == Classification(
        intent="ask_availability",
        proposed_time=None,
        matched_hold=None,
        earliest_offer_time=None,
        new_proposed_time=None,
    )


def test_classify_email_ask_availability_parses_earliest_offer_time():
    earliest = "2026-07-13T00:00:00+00:00"
    client = _client_with_result(
        intent="ask_availability", earliest_offer_time=earliest
    )

    result = classify_email(client, MESSAGE, "Maybe next week?", NOW, [])

    assert result == Classification(
        intent="ask_availability",
        proposed_time=None,
        matched_hold=None,
        earliest_offer_time=datetime.fromisoformat(earliest),
        new_proposed_time=None,
    )


def test_classify_email_ask_availability_parses_z_suffixed_earliest_offer_time():
    client = _client_with_result(
        intent="ask_availability", earliest_offer_time="2026-07-13T00:00:00Z"
    )

    result = classify_email(client, MESSAGE, "Maybe next week?", NOW, [])

    assert result.earliest_offer_time == datetime.fromisoformat(
        "2026-07-13T00:00:00+00:00"
    )


def test_classify_email_ask_availability_falls_back_to_none_on_unparseable_earliest():
    client = _client_with_result(
        intent="ask_availability", earliest_offer_time="not-a-date"
    )

    result = classify_email(client, MESSAGE, "Maybe next week?", NOW, [])

    # Unlike proposed_time, a malformed earliest_offer_time does NOT
    # downgrade the whole classification - it's an optional refinement,
    # not required for ask_availability to be actionable.
    assert result == Classification(
        intent="ask_availability",
        proposed_time=None,
        matched_hold=None,
        earliest_offer_time=None,
        new_proposed_time=None,
    )


def test_classify_email_ask_availability_falls_back_to_none_on_naive_earliest():
    client = _client_with_result(
        intent="ask_availability", earliest_offer_time="2026-07-13T00:00:00"
    )

    result = classify_email(client, MESSAGE, "Maybe next week?", NOW, [])

    assert result == Classification(
        intent="ask_availability",
        proposed_time=None,
        matched_hold=None,
        earliest_offer_time=None,
        new_proposed_time=None,
    )


def test_classify_email_earliest_offer_time_ignored_for_propose_time_intent():
    client = _client_with_result(
        intent="propose_time",
        proposed_time="2026-07-09T14:00:00+00:00",
        earliest_offer_time="2026-07-13T00:00:00+00:00",
        new_proposed_time=None,
    )

    result = classify_email(client, MESSAGE, "Let's meet Thursday at 2pm", NOW, [])

    assert result.earliest_offer_time is None


def test_classify_email_earliest_offer_time_ignored_for_accept_slot_intent():
    holds = [Hold(id="hold-1", thread_id="thread-1", start=NOW, end=NOW, created=NOW)]
    client = _client_with_result(
        intent="accept_slot",
        accepted_slot_index=1,
        earliest_offer_time="2026-07-13T00:00:00+00:00",
        new_proposed_time=None,
    )

    result = classify_email(client, MESSAGE, "Sounds good", NOW, holds)

    assert result.earliest_offer_time is None


def test_classify_email_earliest_offer_time_ignored_for_irrelevant_intent():
    client = _client_with_result(
        intent="irrelevant", earliest_offer_time="2026-07-13T00:00:00+00:00"
    )

    result = classify_email(client, MESSAGE, "50% off everything!", NOW, [])

    assert result.earliest_offer_time is None


def test_classify_email_accept_slot_maps_index_to_hold():
    holds = [
        Hold(id="hold-1", thread_id="thread-1", start=NOW, end=NOW, created=NOW),
        Hold(id="hold-2", thread_id="thread-1", start=NOW, end=NOW, created=NOW),
    ]
    client = _client_with_result(
        intent="accept_slot", proposed_time=None, accepted_slot_index=2
    )

    result = classify_email(client, MESSAGE, "Option 2 works!", NOW, holds)

    assert result.intent == "accept_slot"
    assert result.matched_hold is holds[1]


def test_classify_email_irrelevant():
    client = _client_with_result(
        intent="irrelevant", proposed_time=None, accepted_slot_index=None
    )

    result = classify_email(client, MESSAGE, "50% off everything!", NOW, [])

    assert result == Classification(
        intent="irrelevant",
        proposed_time=None,
        matched_hold=None,
        earliest_offer_time=None,
        new_proposed_time=None,
    )


def test_classify_email_downgrades_out_of_range_slot_index_to_irrelevant():
    holds = [Hold(id="hold-1", thread_id="thread-1", start=NOW, end=NOW, created=NOW)]
    client = _client_with_result(
        intent="accept_slot", proposed_time=None, accepted_slot_index=5
    )

    result = classify_email(client, MESSAGE, "Sounds good", NOW, holds)

    assert result == Classification(
        intent="irrelevant",
        proposed_time=None,
        matched_hold=None,
        earliest_offer_time=None,
        new_proposed_time=None,
    )


def test_classify_email_downgrades_unparseable_proposed_time_to_irrelevant():
    client = _client_with_result(
        intent="propose_time", proposed_time="not-a-date", accepted_slot_index=None
    )

    result = classify_email(client, MESSAGE, "Let's meet soon", NOW, [])

    assert result == Classification(
        intent="irrelevant",
        proposed_time=None,
        matched_hold=None,
        earliest_offer_time=None,
        new_proposed_time=None,
    )


def test_classify_email_downgrades_naive_proposed_time_to_irrelevant():
    client = _client_with_result(
        intent="propose_time",
        proposed_time="2026-07-09T14:00:00",
        accepted_slot_index=None,
    )

    result = classify_email(client, MESSAGE, "Let's meet Thursday at 2pm", NOW, [])

    assert result == Classification(
        intent="irrelevant",
        proposed_time=None,
        matched_hold=None,
        earliest_offer_time=None,
        new_proposed_time=None,
    )


def test_classify_email_raises_value_error_when_no_parsed_result_returned():
    client = _client_with_no_parsed_result()

    with pytest.raises(ValueError):
        classify_email(client, MESSAGE, "body", NOW, [])


def test_classify_email_error_includes_finish_reason_for_diagnosis():
    client = _client_with_no_parsed_result(finish_reason="MAX_TOKENS")

    with pytest.raises(ValueError, match="MAX_TOKENS"):
        classify_email(client, MESSAGE, "body", NOW, [])


def test_classify_email_error_handles_missing_candidates_gracefully():
    response = MagicMock()
    response.parsed = None
    response.candidates = []
    client = MagicMock()
    client.models.generate_content.return_value = response

    with pytest.raises(ValueError, match="unknown"):
        classify_email(client, MESSAGE, "body", NOW, [])


def test_classify_email_raises_value_error_for_naive_now():
    client = _client_with_result(
        intent="irrelevant", proposed_time=None, accepted_slot_index=None
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
    client = _client_with_result(
        intent="irrelevant", proposed_time=None, accepted_slot_index=None
    )

    classify_email(client, MESSAGE, "body", NOW, holds)

    _, kwargs = client.models.generate_content.call_args
    prompt = kwargs["contents"]
    assert "Option 1:" in prompt
    assert "Option 2:" in prompt


def test_classify_email_cancel_or_reschedule_with_no_new_time_is_a_plain_cancel():
    client = _client_with_result(intent="cancel_or_reschedule", new_proposed_time=None)

    result = classify_email(client, MESSAGE, "Please cancel our meeting", NOW, [])

    assert result == Classification(
        intent="cancel_or_reschedule",
        proposed_time=None,
        matched_hold=None,
        earliest_offer_time=None,
        new_proposed_time=None,
    )


def test_classify_email_cancel_or_reschedule_parses_new_proposed_time():
    new_time = "2026-07-10T15:00:00+00:00"
    client = _client_with_result(
        intent="cancel_or_reschedule", new_proposed_time=new_time
    )

    result = classify_email(
        client, MESSAGE, "Can we move to Friday at 3pm instead?", NOW, []
    )

    assert result == Classification(
        intent="cancel_or_reschedule",
        proposed_time=None,
        matched_hold=None,
        earliest_offer_time=None,
        new_proposed_time=datetime.fromisoformat(new_time),
    )


def test_classify_email_cancel_or_reschedule_parses_z_suffixed_new_time():
    client = _client_with_result(
        intent="cancel_or_reschedule", new_proposed_time="2026-07-10T15:00:00Z"
    )

    result = classify_email(client, MESSAGE, "Move to Friday at 3pm UTC?", NOW, [])

    assert result.new_proposed_time == datetime.fromisoformat(
        "2026-07-10T15:00:00+00:00"
    )


def test_classify_email_downgrades_unparseable_new_proposed_time_to_irrelevant():
    client = _client_with_result(
        intent="cancel_or_reschedule", new_proposed_time="not-a-date"
    )

    result = classify_email(
        client, MESSAGE, "Can we move it to sometime else?", NOW, []
    )

    assert result == Classification(
        intent="irrelevant",
        proposed_time=None,
        matched_hold=None,
        earliest_offer_time=None,
        new_proposed_time=None,
    )


def test_classify_email_downgrades_naive_new_proposed_time_to_irrelevant():
    client = _client_with_result(
        intent="cancel_or_reschedule", new_proposed_time="2026-07-10T15:00:00"
    )

    result = classify_email(client, MESSAGE, "Can we move it to Friday 3pm?", NOW, [])

    assert result == Classification(
        intent="irrelevant",
        proposed_time=None,
        matched_hold=None,
        earliest_offer_time=None,
        new_proposed_time=None,
    )


def test_classify_email_uses_correct_model_and_response_schema():
    client = _client_with_result(
        intent="irrelevant", proposed_time=None, accepted_slot_index=None
    )

    classify_email(client, MESSAGE, "body", NOW, [])

    _, kwargs = client.models.generate_content.call_args
    assert kwargs["model"] == GEMINI_MODEL
    assert kwargs["config"].response_mime_type == "application/json"
    assert kwargs["config"].response_schema is ClassificationResult
    # Locks in the thinking_budget=0 fix - a regression here would silently
    # reintroduce the real MAX_TOKENS truncation failure this guards against.
    assert kwargs["config"].thinking_config.thinking_budget == 0
