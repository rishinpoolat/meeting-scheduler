"""Gemini-based reply drafting - one concrete function per calendar outcome."""

import re
from datetime import datetime
from typing import Any

from google.genai import types

from config import GEMINI_MODEL
from gcalendar.events import Hold
from gcalendar.slots import TimeSlot
from gmail.read import Message

DRAFT_MAX_OUTPUT_TOKENS = 1024

# Belt-and-suspenders fallback for _intro()'s "no subject line" prompt
# instruction, which isn't a 100% reliable guarantee against Gemini
# output habits.
_LEADING_SUBJECT_LINE = re.compile(r"^subject:.*(\n|$)", re.IGNORECASE)

# Gemini is asked to leave these literal tokens where a time/list belongs
# rather than writing the value itself - it has proven unreliable at
# reproducing an exact time without corrupting it (see spec). Python
# substitutes the guaranteed-correct value in afterward.
_MEETING_TIME_PLACEHOLDER = "[[MEETING_TIME]]"
_SLOT_LIST_PLACEHOLDER = "[[SLOT_LIST]]"


def draft_booking_confirmation(
    client: Any, message: Message, start: datetime, end: datetime, your_name: str
) -> str:
    """Draft a reply confirming a newly booked meeting."""
    prompt = (
        f"{_intro(message, your_name)}\n\n"
        "Their proposed meeting has been booked. Write a short, friendly "
        "email reply confirming the booking. Insert the literal placeholder "
        f"text {_MEETING_TIME_PLACEHOLDER} exactly once, at the point where "
        "you would naturally state the meeting time - do not write out any "
        "date or time yourself; the placeholder will be replaced "
        "automatically."
    )
    return _complete_with_placeholder(
        client, prompt, _MEETING_TIME_PLACEHOLDER, _format_range(start, end)
    )


def draft_time_unavailable(
    client: Any,
    message: Message,
    requested_start: datetime,
    requested_end: datetime,
    your_name: str,
) -> str:
    """Draft a reply saying the sender's requested time is not available."""
    prompt = (
        f"{_intro(message, your_name)}\n\n"
        "They proposed a meeting time, but that time is not available. "
        "Write a short, friendly email reply letting them know that time "
        "doesn't work, without proposing an alternative time yourself. "
        "Insert the literal placeholder text "
        f"{_MEETING_TIME_PLACEHOLDER} exactly once, at the point where you "
        "would naturally refer to their requested time - do not write out "
        "any date or time yourself; the placeholder will be replaced "
        "automatically."
    )
    return _complete_with_placeholder(
        client,
        prompt,
        _MEETING_TIME_PLACEHOLDER,
        _format_range(requested_start, requested_end),
    )


def draft_slot_offer(
    client: Any, message: Message, slots: list[TimeSlot], your_name: str
) -> str:
    """Draft a reply listing open slots for the sender to choose from."""
    if not slots:
        prompt = (
            f"{_intro(message, your_name)}\n\n"
            "They asked about availability, but there are no open times to "
            "offer right now. Write a short, friendly email reply letting "
            "them know nothing is currently available, without inventing "
            "or writing out any specific times yourself."
        )
        return _complete(client, prompt)

    slot_list = "\n".join(f"- {_format_range(slot.start, slot.end)}" for slot in slots)
    prompt = (
        f"{_intro(message, your_name)}\n\n"
        "They asked about availability. Write a short, friendly email "
        "reply offering some open times and asking them to pick one. "
        "Insert the literal placeholder text "
        f"{_SLOT_LIST_PLACEHOLDER} exactly once, alone on its own line, at "
        "the point where the list of times belongs - do not write out any "
        "dates, times, or a list yourself; the placeholder will be "
        "replaced automatically with the actual list."
    )
    return _complete_with_placeholder(client, prompt, _SLOT_LIST_PLACEHOLDER, slot_list)


def draft_slot_confirmed(
    client: Any, message: Message, hold: Hold, your_name: str
) -> str:
    """Draft a reply confirming which previously offered slot was accepted."""
    prompt = (
        f"{_intro(message, your_name)}\n\n"
        "They accepted one of the previously offered slots. Write a short, "
        "friendly email reply confirming that time is booked. Insert the "
        f"literal placeholder text {_MEETING_TIME_PLACEHOLDER} exactly "
        "once, at the point where you would naturally state the confirmed "
        "time - do not write out any date or time yourself; the "
        "placeholder will be replaced automatically."
    )
    return _complete_with_placeholder(
        client, prompt, _MEETING_TIME_PLACEHOLDER, _format_range(hold.start, hold.end)
    )


def _intro(message: Message, your_name: str) -> str:
    name = _greeting_name(message.from_address)
    return (
        f"You are {your_name}, replying to {name} about: {message.subject}. "
        f'End with a closing line (e.g. "Best,") on its own line, followed '
        f"by your name, {your_name}, on the next line. Write only the email "
        'body text - do not include a subject line or a "Subject:" prefix, '
        "since the subject is set separately."
    )


def _format_date(dt: datetime) -> str:
    """e.g. "Monday, July 13, 2026" - dt.day used directly (not strftime's
    zero-padded %d) so the day never gets a leading zero, without relying
    on the non-portable %-d strftime extension."""
    return f"{dt.strftime('%A, %B')} {dt.day}, {dt.year}"


def _format_time(dt: datetime) -> str:
    """e.g. "1:00 PM" - 12-hour clock with the leading zero stripped."""
    text = dt.strftime("%I:%M %p")
    return text[1:] if text.startswith("0") else text


def _format_range(start: datetime, end: datetime) -> str:
    return f"{_format_date(start)} from {_format_time(start)} to {_format_time(end)}"


def _greeting_name(from_address: str) -> str:
    """Extract a display name from a "From" header, falling back to the
    local part of the email address if there's no display name."""
    match = re.match(r'^\s*"?([^"<]+?)"?\s*<', from_address)
    if match:
        return match.group(1).strip()
    return from_address.split("@")[0].strip()


def _complete(client: Any, prompt: str) -> str:
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=DRAFT_MAX_OUTPUT_TOKENS,
            # Same fix as llm/classify.py: without this, gemini-2.5-flash's
            # internal "thinking" tokens share this budget and could silently
            # truncate the reply text (no response_schema here to detect it
            # via a parse failure - a truncated draft would otherwise slip
            # through as a non-empty response.text with no error raised).
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    if not response.text:
        raise ValueError("Gemini response contained no text")
    text = str(response.text).strip()
    return _LEADING_SUBJECT_LINE.sub("", text, count=1).strip()


def _complete_with_placeholder(
    client: Any, prompt: str, placeholder: str, replacement: str
) -> str:
    """Like `_complete`, but requires `placeholder` to occur exactly once in
    the response and substitutes it with `replacement` - raises ValueError
    instead of silently drafting a reply with an unverified, missing, or
    duplicated (which `str.replace(..., 1)` would only partially fix,
    leaving a literal placeholder in the final text) time. This lands in
    agent.py's existing per-message try/except (leaves the message
    unread, retries next run), the same safe-failure path already used
    for other malformed-response cases.
    """
    text = _complete(client, prompt)
    if text.count(placeholder) != 1:
        raise ValueError(
            f"Gemini response did not contain expected placeholder "
            f"{placeholder!r} exactly once (found {text.count(placeholder)})"
        )
    return text.replace(placeholder, replacement, 1)
