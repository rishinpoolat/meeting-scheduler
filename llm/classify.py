"""Gemini-based intent classification and datetime/slot extraction for inbound emails."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from google.genai import types
from pydantic import BaseModel, Field

from config import GEMINI_MODEL
from gcalendar.events import Hold
from gmail.read import Message

Intent = Literal["propose_time", "ask_availability", "accept_slot", "irrelevant"]

CLASSIFY_MAX_OUTPUT_TOKENS = 512


class ClassificationResult(BaseModel):
    intent: Intent = Field(
        description=(
            "propose_time: sender proposes a specific date/time to meet. "
            "ask_availability: sender asks when you're free, without "
            "proposing a time. accept_slot: sender is replying to accept "
            "one of the previously offered candidate slots listed below. "
            "irrelevant: anything else (spam, newsletters, unrelated "
            "correspondence)."
        )
    )
    proposed_time: str | None = Field(
        description=(
            "ISO 8601 datetime with UTC offset, computed relative to the "
            "current date/time given below. Set only when intent is "
            "propose_time; null otherwise."
        )
    )
    earliest_offer_time: str | None = Field(
        description=(
            "ISO 8601 datetime with UTC offset, computed relative to the "
            "current date/time given below, representing the earliest "
            "moment slots should be offered from. Set only when intent is "
            "ask_availability AND the sender expressed a timeframe "
            'preference (e.g. "next week", "not this week", "after '
            'the 20th", "sometime next month"). Null when intent is '
            "ask_availability with no stated timeframe preference (offer "
            "starting now), and null for every other intent."
        )
    )
    accepted_slot_index: int | None = Field(
        description=(
            "1-based index into the numbered candidate slots list below. "
            "Set only when intent is accept_slot; null otherwise."
        )
    )


@dataclass
class Classification:
    intent: Intent
    proposed_time: datetime | None
    matched_hold: Hold | None
    earliest_offer_time: datetime | None


def classify_email(
    client: Any,
    message: Message,
    body: str,
    now: datetime,
    candidate_holds: list[Hold],
) -> Classification:
    """Classify an email's scheduling intent using Gemini structured output.

    `now` must be timezone-aware (raises ValueError otherwise) - it's the
    reference point Gemini uses to resolve relative dates like "next Tuesday".
    `candidate_holds` are this thread's currently-open holds (possibly empty);
    they're shown to Gemini as a numbered list so it can flag which one a
    reply is accepting without ever being trusted to echo back a real
    Calendar event ID.
    """
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    prompt = _build_prompt(message, body, now, candidate_holds)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ClassificationResult,
            max_output_tokens=CLASSIFY_MAX_OUTPUT_TOKENS,
        ),
    )

    result = response.parsed
    if result is None:
        raise ValueError("Gemini response did not contain a parsed classification")

    return _to_classification(result, candidate_holds)


def _build_prompt(
    message: Message, body: str, now: datetime, candidate_holds: list[Hold]
) -> str:
    lines = [
        f"Current date/time: {now.strftime('%A, %Y-%m-%d %H:%M %z')}",
        f"From: {message.from_address}",
        f"Subject: {message.subject}",
        "",
        "Email body:",
        body,
    ]
    if candidate_holds:
        lines.append("")
        lines.append("This thread previously offered the sender these candidate slots:")
        for i, hold in enumerate(candidate_holds, start=1):
            lines.append(
                f"Option {i}: {hold.start.strftime('%A, %Y-%m-%d %H:%M')} "
                f"to {hold.end.strftime('%H:%M')}"
            )
    lines.append("")
    lines.append("Classify this email's scheduling intent.")
    return "\n".join(lines)


def _to_classification(
    result: ClassificationResult, candidate_holds: list[Hold]
) -> Classification:
    intent = result.intent

    if intent == "propose_time":
        proposed_time = _parse_iso_datetime(result.proposed_time)
        if proposed_time is None:
            return Classification(
                intent="irrelevant",
                proposed_time=None,
                matched_hold=None,
                earliest_offer_time=None,
            )
        return Classification(
            intent="propose_time",
            proposed_time=proposed_time,
            matched_hold=None,
            earliest_offer_time=None,
        )

    if intent == "ask_availability":
        return Classification(
            intent="ask_availability",
            proposed_time=None,
            matched_hold=None,
            earliest_offer_time=_parse_iso_datetime(result.earliest_offer_time),
        )

    if intent == "accept_slot":
        matched_hold = _match_hold(result.accepted_slot_index, candidate_holds)
        if matched_hold is None:
            return Classification(
                intent="irrelevant",
                proposed_time=None,
                matched_hold=None,
                earliest_offer_time=None,
            )
        return Classification(
            intent="accept_slot",
            proposed_time=None,
            matched_hold=matched_hold,
            earliest_offer_time=None,
        )

    return Classification(
        intent=intent,
        proposed_time=None,
        matched_hold=None,
        earliest_offer_time=None,
    )


def _parse_iso_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def _match_hold(index: Any, candidate_holds: list[Hold]) -> Hold | None:
    if not isinstance(index, int):
        return None
    if index < 1 or index > len(candidate_holds):
        return None
    return candidate_holds[index - 1]
