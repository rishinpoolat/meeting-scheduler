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


def draft_booking_confirmation(
    client: Any, message: Message, start: datetime, end: datetime
) -> str:
    """Draft a reply confirming a newly booked meeting."""
    prompt = (
        f"{_intro(message)}\n\n"
        "Their proposed meeting has been booked for "
        f"{_format_range(start, end)}. Write a short, friendly email reply "
        "confirming the booking."
    )
    return _complete(client, prompt)


def draft_time_unavailable(
    client: Any, message: Message, requested_start: datetime, requested_end: datetime
) -> str:
    """Draft a reply saying the sender's requested time is not available."""
    prompt = (
        f"{_intro(message)}\n\n"
        f"They proposed meeting at {_format_range(requested_start, requested_end)}, "
        "but that time is not available. Write a short, friendly email reply "
        "letting them know that time doesn't work, without proposing an "
        "alternative time yourself."
    )
    return _complete(client, prompt)


def draft_slot_offer(client: Any, message: Message, slots: list[TimeSlot]) -> str:
    """Draft a reply listing open slots for the sender to choose from."""
    slot_lines = "\n".join(f"- {_format_range(slot.start, slot.end)}" for slot in slots)
    prompt = (
        f"{_intro(message)}\n\n"
        "They asked about availability. Write a short, friendly email reply "
        f"offering these open times and asking them to pick one:\n{slot_lines}"
    )
    return _complete(client, prompt)


def draft_slot_confirmed(client: Any, message: Message, hold: Hold) -> str:
    """Draft a reply confirming which previously offered slot was accepted."""
    prompt = (
        f"{_intro(message)}\n\n"
        f"They accepted the {_format_range(hold.start, hold.end)} slot. Write a "
        "short, friendly email reply confirming that time is booked."
    )
    return _complete(client, prompt)


def _intro(message: Message) -> str:
    name = _greeting_name(message.from_address)
    return f"You're replying to {name} about: {message.subject}"


def _format_range(start: datetime, end: datetime) -> str:
    return f"{start.strftime('%A, %Y-%m-%d %H:%M')} to {end.strftime('%H:%M')}"


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
        config=types.GenerateContentConfig(max_output_tokens=DRAFT_MAX_OUTPUT_TOKENS),
    )
    if not response.text:
        raise ValueError("Gemini response contained no text")
    return str(response.text).strip()
