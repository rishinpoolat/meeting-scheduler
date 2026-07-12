# Spec: Respect the sender's stated timeframe when offering availability

**Status:** Approved
**Created:** 2026-07-12

## What it does

When a sender asks for availability and states a timeframe preference
(e.g. "maybe next week"), the agent now offers slots starting from
that preference instead of always starting from `now`.

## Decisions

- New field `ClassificationResult.earliest_offer_time: str | None` —
  same type/semantics as `proposed_time` (ISO 8601 datetime with UTC
  offset, Gemini-computed relative to the `now` already given in the
  prompt), meaning "the earliest moment slots should be offered
  from." Set only when intent is `ask_availability` and the sender
  expressed a timeframe preference; null otherwise (including
  `ask_availability` with no stated preference — offer starts from
  `now`, unchanged from today). No new prompt-building logic needed —
  `proposed_time` already proves Gemini can do this relative-date
  reasoning off the existing `"Current date/time: ..."` line.
- `Classification` dataclass gets a 4th field, `earliest_offer_time:
  datetime | None`, appended, no default (matches existing style).
- Parsing reuses the existing ISO-datetime parser (renamed
  `_parse_proposed_time` → `_parse_iso_datetime`, now shared). On
  failure (unparseable or naive), falls back to `None` rather than
  downgrading the whole classification to `irrelevant`. This is a
  deliberate asymmetry from `proposed_time`'s downgrade rule, but the
  *same underlying criterion* the existing spec states for that rule
  ("downgrading is the only choice that can never cause an incorrect
  auto-book or false accept-confirmation"): `proposed_time` /
  `accepted_slot_index` are required for their intents to mean
  anything, so bad data must downgrade. `earliest_offer_time` is an
  optional refinement — `_handle_ask_availability` is fully
  actionable with `None` (today's behavior for every
  `ask_availability` email). Downgrading on a malformed *optional*
  field would regress a working path (no draft sent) to fix a smaller
  problem.
- `find_open_slots(service, count=5, now=None, earliest=None)` — new
  `earliest: datetime | None` param (generic name at this layer;
  `gcalendar/slots.py` has no "offer" concept). Validated tz-aware
  like `now`. Effective start becomes `max(current,
  earliest.astimezone(tz))` — only ever pushes later, never earlier
  than `now`, clamped silently (no logging path exists for this kind
  of soft mismatch in this codebase). Far-future or weekend `earliest`
  values are already handled correctly for free by the existing
  `_half_day_windows` walk/rounding logic.
- `agent.py`'s `_handle_ask_availability` gains an `earliest_offer_time:
  datetime | None` param, threaded from
  `classification.earliest_offer_time` into `find_open_slots`.

## Open questions

None — resolved via a Plan-agent design review before implementation.

## Out of scope

- `llm/draft.py`'s `draft_slot_offer` does not need
  `earliest_offer_time` — the reply already just lists whatever slots
  were found; since those now correctly start after the stated
  preference, no extra phrasing is needed.
- No new prompt-building logic beyond the new field's own description.

## Affected areas

- `llm/classify.py`, `gcalendar/slots.py`, `agent.py`
- `tests/test_llm_classify.py`, `tests/test_gcalendar_slots.py`,
  `tests/test_agent.py`
- `CODEBASE_MAP.md`
