"""Gemini-based intent classification and datetime/slot extraction for inbound emails."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from google.genai import types
from pydantic import BaseModel, Field

from config import GEMINI_MODEL
from gcalendar.events import Hold
from gmail.read import Message

Intent = Literal[
    "propose_time",
    "ask_availability",
    "accept_slot",
    "cancel_or_reschedule",
    "irrelevant",
]

# Gemini flash models' "thinking" tokens otherwise share this same budget
# (AUTOMATIC by default) before any JSON is emitted, which can silently
# truncate the response on a more complex email. thinking_budget=0
# (fully disabled) previously worked but started returning 400
# INVALID_ARGUMENT after a server-side model upgrade; -1 (dynamic,
# model-chosen budget) is accepted across model generations and still
# avoids the AUTOMATIC default's larger, truncation-prone budget.
CLASSIFY_MAX_OUTPUT_TOKENS = 1024


class ClassificationResult(BaseModel):
    intent: Intent = Field(
        description=(
            "propose_time: sender proposes a specific date/time to meet. "
            "ask_availability: sender asks when you're free, without "
            "proposing a time. accept_slot: sender is replying to accept "
            "one of the previously offered candidate slots listed below. "
            "cancel_or_reschedule: sender wants to cancel an existing "
            "meeting, or move it to a different time. irrelevant: "
            "anything else (spam, newsletters, unrelated correspondence)."
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
    new_proposed_time: str | None = Field(
        description=(
            "ISO 8601 datetime with UTC offset, computed relative to the "
            "current date/time given below. Set only when intent is "
            "cancel_or_reschedule AND the sender named a specific new "
            "time to move the meeting to; null when they're asking to "
            "cancel outright (no new time), and null for every other "
            "intent."
        )
    )


@dataclass
class Classification:
    intent: Intent
    proposed_time: datetime | None
    matched_hold: Hold | None
    earliest_offer_time: datetime | None
    new_proposed_time: datetime | None


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
            thinking_config=types.ThinkingConfig(thinking_budget=-1),
        ),
    )

    result = response.parsed
    if result is None:
        raise ValueError(
            "Gemini response did not contain a parsed classification "
            f"(finish_reason={_finish_reason(response)})"
        )

    return _to_classification(result, candidate_holds)


def _finish_reason(response: Any) -> str:
    """Best-effort diagnostic for a response that failed to parse - e.g.
    MAX_TOKENS (output got cut off, raise CLASSIFY_MAX_OUTPUT_TOKENS) vs.
    SAFETY (content filtered) point to very different fixes."""
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return "unknown"
    return str(getattr(candidates[0], "finish_reason", "unknown"))


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
    lines.append(
        "If the sender is asking to cancel or move an existing meeting, "
        "use intent cancel_or_reschedule. If they name a specific new "
        "time to move it to, set new_proposed_time; if they just want to "
        "cancel with no new time, leave new_proposed_time null."
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
                new_proposed_time=None,
            )
        return Classification(
            intent="propose_time",
            proposed_time=proposed_time,
            matched_hold=None,
            earliest_offer_time=None,
            new_proposed_time=None,
        )

    if intent == "ask_availability":
        return Classification(
            intent="ask_availability",
            proposed_time=None,
            matched_hold=None,
            earliest_offer_time=_parse_iso_datetime(result.earliest_offer_time),
            new_proposed_time=None,
        )

    if intent == "accept_slot":
        matched_hold = _match_hold(result.accepted_slot_index, candidate_holds)
        if matched_hold is None:
            return Classification(
                intent="irrelevant",
                proposed_time=None,
                matched_hold=None,
                earliest_offer_time=None,
                new_proposed_time=None,
            )
        return Classification(
            intent="accept_slot",
            proposed_time=None,
            matched_hold=matched_hold,
            earliest_offer_time=None,
            new_proposed_time=None,
        )

    if intent == "cancel_or_reschedule":
        # A raw new_proposed_time string that fails to parse is ambiguous
        # (did the sender name a new time or not?) - downgrade rather than
        # guess, same rule as propose_time's proposed_time above.
        if result.new_proposed_time is not None:
            new_proposed_time = _parse_iso_datetime(result.new_proposed_time)
            if new_proposed_time is None:
                return Classification(
                    intent="irrelevant",
                    proposed_time=None,
                    matched_hold=None,
                    earliest_offer_time=None,
                    new_proposed_time=None,
                )
        else:
            new_proposed_time = None
        return Classification(
            intent="cancel_or_reschedule",
            proposed_time=None,
            matched_hold=None,
            earliest_offer_time=None,
            new_proposed_time=new_proposed_time,
        )

    return Classification(
        intent=intent,
        proposed_time=None,
        matched_hold=None,
        earliest_offer_time=None,
        new_proposed_time=None,
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
