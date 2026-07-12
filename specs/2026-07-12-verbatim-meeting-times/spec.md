# Spec: Drafted meeting times can be silently corrupted by Gemini

**Status:** Approved
**Created:** 2026-07-12

## What it does

Guarantees that a meeting time shown in a drafted reply is always
exactly correct, by never letting Gemini reformat/reproduce the actual
time value itself.

## Decisions

- Root cause: `llm/draft.py`'s four draft functions gave Gemini a
  pre-formatted time string and asked it to naturally incorporate it
  into prose (including a 24h→12h conversion). Confirmed via live
  Gemini calls and real Calendar inspection that this non-
  deterministically corrupts the value — `_format_range()` itself is
  100% correct, the corruption happens during Gemini's free-text
  reformatting.
- Fix: placeholder substitution. Gemini writes prose around a literal
  token (`[[MEETING_TIME]]` or `[[SLOT_LIST]]`) it's told not to
  replace itself; Python substitutes the guaranteed-correct value
  afterward. The exact-correct string never passes through the model.
- Rejected alternatives: verbatim substring matching (Gemini's
  stylistic variance makes this either too strict or too loose to
  reliably catch corruption) and structured JSON output (still has
  Gemini echo the time value, doesn't structurally prevent
  corruption, just relocates it).
- If the placeholder is missing from Gemini's response, raise
  `ValueError` — lands in `agent.py`'s already-established
  safe-failure path (log, leave unread, retry next run). A
  corrupted/missing time can never silently reach a drafted email.
- `draft_slot_offer` with empty `slots` skips the placeholder path
  entirely (nothing time-bearing to protect).
- `_format_range()` now produces a friendly 12-hour phrase directly in
  Python instead of 24-hour text for Gemini to convert.

## Open questions

None — resolved via a Plan-agent design review before implementation.

## Out of scope

- `llm/classify.py`'s own datetime formatting — different risk
  profile (Gemini's input for matching, not output it must
  reproduce).
- Live end-to-end verification against the real Gemini API — blocked
  by the free tier's exhausted daily quota (20 requests/day) today;
  deferred as a required follow-up once it resets.

## Affected areas

- `llm/draft.py`
- `tests/test_llm_draft.py`
- `CODEBASE_MAP.md`
