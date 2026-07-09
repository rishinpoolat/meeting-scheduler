# Spec: agent.py — wire the full cycle

**Status:** Approved
**Created:** 2026-07-09

## What it does

`agent.py` orchestrates one Gmail-polling cycle: for every unread
message, classify its scheduling intent (via `llm/`) and act on it —
book a confirmed meeting, offer open slots as tentative holds, confirm
one of a thread's previously-offered holds, or skip irrelevant email —
then create a Gmail draft reply. This is Feature 5 in
`specs/ROADMAP.md`, the first point where Features 1–4 (auth, Gmail
read/draft, Calendar holds, Gemini classify/draft) get wired together.

## Decisions

- **No mark-as-read.** `gmail/` has no such function today, and
  ROADMAP explicitly assigns "dedupe/mark-processed handling" to
  Feature 6. Running `python agent.py` twice on the same unread inbox
  redrafts replies for the same messages until Feature 6 lands —
  accepted as a known limitation for now.
- **`expire_stale_holds()` is not called from this feature**, even
  though it already exists (built in Feature 3) — also deferred to
  Feature 6, which owns wiring the sweep into the scheduled loop.
- **Accept-slot-on-an-already-expired-hold limitation accepted as-is.**
  Once a hold is swept, there's no persisted record of what it was, so
  `classify_email` can't distinguish "genuinely irrelevant reply" from
  "trying to accept a since-expired offer" — both downgrade to
  `intent="irrelevant"`. `agent.py` treats this like any other
  irrelevant email (skip, no draft, no calendar write). ROADMAP's
  original guess ("re-check freebusy and book if still free") isn't
  achievable without schema changes to the already-shipped
  `llm/classify.py`, so it's explicitly out of scope here.
- **Meeting duration for `propose_time`** = `SLOT_DURATION` (30 min,
  from `gcalendar/slots.py`), reused since `classify_email` only
  returns a proposed start time, no duration.
- **Past-proposed-time guard.** If Gemini extracts a `proposed_time`
  that's not after `now` (a misextraction, since freebusy alone can't
  catch this — nothing's ever "busy" in the past), `agent.py` treats it
  like a busy slot: drafts `draft_time_unavailable` and does not call
  `is_slot_free`/`book_event`. Added after code review flagged that a
  past-time misextraction would otherwise get silently booked.
- **`list_holds(cal_service, thread_id=message.thread_id)` is called
  unconditionally** before classification, for every message
  regardless of eventual intent — this is what wires thread-hold
  acceptance matching in; an empty list is fine for a fresh thread.
- **No per-message error isolation in `run_cycle`.** One bad message
  aborts the rest of the cycle; partial progress (earlier drafts/holds
  in the same run) is not rolled back. Matches deferring "basic error
  logging" to Feature 6.
- **Bare-email extraction** (`email.utils.parseaddr` on
  `message.from_address`) lives as a private helper in `agent.py`,
  since Calendar's `attendee_email` param rejects `"Name <addr>"`
  formatting and no other module needs this parsing yet.

## Open questions

(none — all resolved above)

## Out of scope

- Marking messages read / dedup / reprocessing guard (Feature 6).
- Calling `expire_stale_holds()` (Feature 6).
- Recovering the original requested time after a hold has expired and
  been swept (not achievable without changing `llm/classify.py`).
- Repeating the cycle on a schedule, and per-message error logging
  (Feature 6).

## Affected areas

- `agent.py` (new)
- `tests/test_agent.py` (new)
- `CODEBASE_MAP.md` (drop `(PLANNED)` marker, describe actual shape)
- `specs/ROADMAP.md`, `specs/INDEX.md` (mark Feature 5 done)
