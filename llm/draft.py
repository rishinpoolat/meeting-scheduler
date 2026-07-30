"""Gemini-based reply drafting - one concrete function per calendar outcome."""

import html
import re
from dataclasses import dataclass
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

# Gemini is asked to leave these literal tokens, alone on their own
# paragraph, where a time/list belongs rather than writing the value
# itself - it has proven unreliable at reproducing an exact time
# without corrupting it (see specs/2026-07-12-verbatim-meeting-times/).
# Python substitutes the guaranteed-correct value in afterward.
_MEETING_TIME_PLACEHOLDER = "[[MEETING_TIME]]"
_SLOT_LIST_PLACEHOLDER = "[[SLOT_LIST]]"


@dataclass
class DraftBody:
    text: str
    html: str


def draft_booking_confirmation(
    client: Any, message: Message, start: datetime, end: datetime, your_name: str
) -> DraftBody:
    """Draft a reply confirming a newly booked meeting."""
    prompt = (
        f"{_intro(message, your_name)}\n\n"
        "Their proposed meeting has been booked. Write a short, friendly "
        "email reply confirming the booking. Insert the literal placeholder "
        f"text {_MEETING_TIME_PLACEHOLDER} on a line by itself, with a "
        "blank line before and after it, at the point where you would "
        "naturally state the meeting time - do not write out any date or "
        "time yourself; the placeholder will be replaced automatically."
    )
    return _complete_with_placeholder(
        client,
        prompt,
        _MEETING_TIME_PLACEHOLDER,
        _format_range(start, end),
        _time_box_html(start, end),
    )


def draft_time_unavailable(
    client: Any,
    message: Message,
    requested_start: datetime,
    requested_end: datetime,
    your_name: str,
) -> DraftBody:
    """Draft a reply saying the sender's requested time is not available."""
    prompt = (
        f"{_intro(message, your_name)}\n\n"
        "They proposed a meeting time, but that time is not available. "
        "Write a short, friendly email reply letting them know that time "
        "doesn't work, without proposing an alternative time yourself. "
        "Insert the literal placeholder text "
        f"{_MEETING_TIME_PLACEHOLDER} on a line by itself, with a blank "
        "line before and after it, at the point where you would naturally "
        "refer to their requested time - do not write out any date or "
        "time yourself; the placeholder will be replaced automatically."
    )
    return _complete_with_placeholder(
        client,
        prompt,
        _MEETING_TIME_PLACEHOLDER,
        _format_range(requested_start, requested_end),
        _time_box_html(requested_start, requested_end),
    )


def draft_slot_offer(
    client: Any, message: Message, slots: list[TimeSlot], your_name: str
) -> DraftBody:
    """Draft a reply listing open slots for the sender to choose from."""
    if not slots:
        prompt = (
            f"{_intro(message, your_name)}\n\n"
            "They asked about availability, but there are no open times to "
            "offer right now. Write a short, friendly email reply letting "
            "them know nothing is currently available, without inventing "
            "or writing out any specific times yourself."
        )
        text = _complete(client, prompt)
        return DraftBody(text=text, html=_paragraphs_to_html(text))

    slot_list = "\n".join(f"- {_format_range(slot.start, slot.end)}" for slot in slots)
    prompt = (
        f"{_intro(message, your_name)}\n\n"
        "They asked about availability. Write a short, friendly email "
        "reply offering some open times and asking them to pick one. "
        "Insert the literal placeholder text "
        f"{_SLOT_LIST_PLACEHOLDER} on a line by itself, with a blank line "
        "before and after it, at the point where the list of times "
        "belongs - do not write out any dates, times, or a list yourself; "
        "the placeholder will be replaced automatically with the actual "
        "list."
    )
    return _complete_with_placeholder(
        client, prompt, _SLOT_LIST_PLACEHOLDER, slot_list, _slot_list_html(slots)
    )


def draft_slot_confirmed(
    client: Any, message: Message, hold: Hold, your_name: str
) -> DraftBody:
    """Draft a reply confirming which previously offered slot was accepted."""
    prompt = (
        f"{_intro(message, your_name)}\n\n"
        "They accepted one of the previously offered slots. Write a short, "
        "friendly email reply confirming that time is booked. Insert the "
        f"literal placeholder text {_MEETING_TIME_PLACEHOLDER} on a line "
        "by itself, with a blank line before and after it, at the point "
        "where you would naturally state the confirmed time - do not "
        "write out any date or time yourself; the placeholder will be "
        "replaced automatically."
    )
    return _complete_with_placeholder(
        client,
        prompt,
        _MEETING_TIME_PLACEHOLDER,
        _format_range(hold.start, hold.end),
        _time_box_html(hold.start, hold.end),
    )


def _intro(message: Message, your_name: str) -> str:
    name = _greeting_name(message.from_address)
    return (
        f"You are {your_name}, replying to {name} about: {message.subject}. "
        f'End with a closing line (e.g. "Best,") on its own line, followed '
        f"by your name, {your_name}, on the next line. Write only the email "
        'body text - do not include a subject line or a "Subject:" prefix, '
        "since the subject is set separately. Write plain prose only - do "
        "not use markdown formatting (no **, _, #, -, or similar syntax)."
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


def _slot_row_html(start: datetime, end: datetime) -> str:
    # _format_date/_format_time output is always machine-generated from
    # strftime (weekday/month names, digits, "AM"/"PM") - never influenced
    # by external input, so it can't contain HTML-special characters.
    return (
        '<td style="border:1px solid #d0d7de;border-radius:8px;'
        'padding:12px 16px;background:#f6f8fa;font-family:sans-serif;">'
        f'<strong style="font-size:15px;color:#24292f;">{_format_date(start)}'
        "</strong><br>"
        f'<span style="color:#57606a;font-size:14px;">{_format_time(start)}'
        f" &ndash; {_format_time(end)}</span>"
        "</td>"
    )


def _time_box_html(start: datetime, end: datetime) -> str:
    return (
        '<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;">'
        f"<tr>{_slot_row_html(start, end)}</tr>"
        "</table>"
    )


def _slot_list_html(slots: list[TimeSlot]) -> str:
    spacer = '<tr><td style="height:8px;line-height:8px;">&nbsp;</td></tr>'
    rows = spacer.join(f"<tr>{_slot_row_html(s.start, s.end)}</tr>" for s in slots)
    return f'<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;">{rows}</table>'


def _paragraph_to_html(paragraph: str) -> str:
    escaped = html.escape(paragraph).replace("\n", "<br>")
    return f'<p style="margin:0 0 12px;">{escaped}</p>'


def _paragraphs_to_html(text: str) -> str:
    return "\n".join(_paragraph_to_html(p) for p in text.split("\n\n") if p.strip())


def _complete(client: Any, prompt: str) -> str:
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=DRAFT_MAX_OUTPUT_TOKENS,
            # Same fix as llm/classify.py: without this, Gemini flash models'
            # internal "thinking" tokens share this budget and could silently
            # truncate the reply text (no response_schema here to detect it
            # via a parse failure - a truncated draft would otherwise slip
            # through as a non-empty response.text with no error raised).
            # thinking_budget=0 (fully disabled) started returning 400
            # INVALID_ARGUMENT after a server-side model upgrade; -1
            # (dynamic budget) is accepted across model generations.
            thinking_config=types.ThinkingConfig(thinking_budget=-1),
        ),
    )
    if not response.text:
        raise ValueError("Gemini response contained no text")
    text = str(response.text).strip()
    return _LEADING_SUBJECT_LINE.sub("", text, count=1).strip()


def _complete_with_placeholder(
    client: Any,
    prompt: str,
    placeholder: str,
    text_replacement: str,
    html_replacement: str,
) -> DraftBody:
    """Like `_complete`, but requires `placeholder` to be alone on its own
    paragraph (blank-line-separated) exactly once, then builds both a
    plain-text and an HTML version of the reply with that paragraph
    substituted.

    Requiring the placeholder on its own paragraph - not just "present
    somewhere" - matters for the HTML version: `html_replacement` is a
    block-level element (a `<table>` box), and substituting a block
    element mid-sentence into a `<p>` produces invalid HTML that real
    renderers silently reflow, breaking the surrounding sentence. Raises
    ValueError if the placeholder is missing, duplicated, or not alone on
    its own line - lands in agent.py's existing per-message try/except
    (leaves the message unread, retries next run), the same safe-failure
    path already used for other malformed-response cases.
    """
    template = _complete(client, prompt)
    paragraphs = template.split("\n\n")
    matches = [i for i, p in enumerate(paragraphs) if p.strip() == placeholder]
    # Paragraph-exact matches alone aren't enough to rule out duplication:
    # a second, mid-sentence copy of the placeholder (not its own
    # paragraph) would pass `len(matches) == 1` but still leak the literal
    # token into the drafted reply. The total substring count catches that.
    if len(matches) != 1 or template.count(placeholder) != 1:
        raise ValueError(
            f"Gemini response did not contain expected placeholder "
            f"{placeholder!r} alone on its own paragraph exactly once "
            f"(found {len(matches)} isolated paragraph(s), "
            f"{template.count(placeholder)} total occurrence(s))"
        )
    index = matches[0]

    text_paragraphs = list(paragraphs)
    text_paragraphs[index] = text_replacement
    text = "\n\n".join(text_paragraphs).strip()

    html_paragraphs = [
        html_replacement if i == index else _paragraph_to_html(p)
        for i, p in enumerate(paragraphs)
    ]
    html_body = "\n".join(html_paragraphs)

    return DraftBody(text=text, html=html_body)
