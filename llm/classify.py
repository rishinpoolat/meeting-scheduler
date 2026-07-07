"""Claude-based intent classification and datetime/slot extraction for inbound emails."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from config import CLAUDE_MODEL
from gcalendar.events import Hold
from gmail.read import Message

Intent = Literal["propose_time", "ask_availability", "accept_slot", "irrelevant"]

CLASSIFY_MAX_TOKENS = 512
CLASSIFY_TOOL_NAME = "record_classification"

CLASSIFY_TOOL = {
    "name": CLASSIFY_TOOL_NAME,
    "description": "Record the classification of an inbound scheduling email.",
    "input_schema": {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "enum": [
                    "propose_time",
                    "ask_availability",
                    "accept_slot",
                    "irrelevant",
                ],
                "description": (
                    "propose_time: sender proposes a specific date/time to meet. "
                    "ask_availability: sender asks when you're free, without "
                    "proposing a time. accept_slot: sender is replying to accept "
                    "one of the previously offered candidate slots listed below. "
                    "irrelevant: anything else (spam, newsletters, unrelated "
                    "correspondence)."
                ),
            },
            "proposed_time": {
                "type": ["string", "null"],
                "description": (
                    "ISO 8601 datetime with UTC offset, computed relative to the "
                    "current date/time given below. Set only when intent is "
                    "propose_time; null otherwise."
                ),
            },
            "accepted_slot_index": {
                "type": ["integer", "null"],
                "description": (
                    "1-based index into the numbered candidate slots list below. "
                    "Set only when intent is accept_slot; null otherwise."
                ),
            },
        },
        "required": ["intent", "proposed_time", "accepted_slot_index"],
    },
}


@dataclass
class Classification:
    intent: Intent
    proposed_time: datetime | None
    matched_hold: Hold | None


def classify_email(
    client: Any,
    message: Message,
    body: str,
    now: datetime,
    candidate_holds: list[Hold],
) -> Classification:
    """Classify an email's scheduling intent using Claude tool use.

    `now` must be timezone-aware (raises ValueError otherwise) - it's the
    reference point Claude uses to resolve relative dates like "next Tuesday".
    `candidate_holds` are this thread's currently-open holds (possibly empty);
    they're shown to Claude as a numbered list so it can flag which one a
    reply is accepting without ever being trusted to echo back a real
    Calendar event ID.
    """
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    prompt = _build_prompt(message, body, now, candidate_holds)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=CLASSIFY_MAX_TOKENS,
        tools=[CLASSIFY_TOOL],
        tool_choice={"type": "tool", "name": CLASSIFY_TOOL_NAME},
        messages=[{"role": "user", "content": prompt}],
    )

    tool_use = next(
        (block for block in response.content if block.type == "tool_use"), None
    )
    if tool_use is None:
        raise ValueError("Claude response did not contain a tool_use block")

    return _to_classification(tool_use.input, candidate_holds)


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
        "Classify this email's scheduling intent and call the "
        f"{CLASSIFY_TOOL_NAME} tool exactly once."
    )
    return "\n".join(lines)


def _to_classification(
    tool_input: dict[str, Any], candidate_holds: list[Hold]
) -> Classification:
    intent: Intent = tool_input["intent"]

    if intent == "propose_time":
        proposed_time = _parse_proposed_time(tool_input.get("proposed_time"))
        if proposed_time is None:
            return Classification(
                intent="irrelevant", proposed_time=None, matched_hold=None
            )
        return Classification(
            intent="propose_time", proposed_time=proposed_time, matched_hold=None
        )

    if intent == "accept_slot":
        matched_hold = _match_hold(
            tool_input.get("accepted_slot_index"), candidate_holds
        )
        if matched_hold is None:
            return Classification(
                intent="irrelevant", proposed_time=None, matched_hold=None
            )
        return Classification(
            intent="accept_slot", proposed_time=None, matched_hold=matched_hold
        )

    return Classification(intent=intent, proposed_time=None, matched_hold=None)


def _parse_proposed_time(value: Any) -> datetime | None:
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
