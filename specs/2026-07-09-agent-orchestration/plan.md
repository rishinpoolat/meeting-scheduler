# Plan: agent.py — wire the full cycle

**Status:** Approved
**Spec:** see ../spec.md
**Branch:** feature/agent-orchestration

## To Do

(nothing left)

## In Progress

(nothing left)

## Completed

- [x] Testing skill's quality gate: test-runner reported 90/90 passing
      (pytest/mypy/ruff all clean); code-reviewer verified every
      `agent.py` call against real `gmail`/`gcalendar`/`llm` signatures
      (all correct) and rated test coverage strong (both branches of
      every intent, no happy-path-only gaps). Reported 2 non-blocking
      findings — developer chose to fix one, leave the other:
      - Fixed: past-`proposed_time` guard added to `_handle_propose_time`
        (treats a non-future proposed time like a busy slot instead of
        booking it) — new test
        `test_propose_time_in_the_past_is_treated_as_unavailable`.
      - Left as-is: `run_cycle`'s separate `get_message`/
        `get_message_body` calls double Gmail API calls per message —
        pre-existing `gmail/read.py` design, not a bug, scoped as a
        future efficiency cleanup rather than bundled here.
- [x] Updated `CODEBASE_MAP.md`, `README.md`, `specs/ROADMAP.md`
      (Feature 5 ✅, "Known open decisions" resolved), `specs/INDEX.md`.

- [x] `agent.py`: `main()`, `run_cycle()`, `process_message()`, and
      per-intent private helpers (`_handle_propose_time`,
      `_handle_ask_availability`, `_handle_accept_slot`,
      `_sender_email`, `_event_summary`) per the approved design.
- [x] Unit tests (`tests/test_agent.py`), dotted-path-patch convention
      (`patch("agent.<name>", ...)`), covering:
      - `process_message` always fetches `list_holds(thread_id=...)`
        before classifying and passes it as `candidate_holds`
      - `irrelevant` intent is a no-op (no booking/hold/draft calls)
      - `propose_time` + free slot → books `(start, start+SLOT_DURATION)`,
        drafts confirmation, creates draft reply
      - `propose_time` + busy slot → no booking, drafts unavailable,
        still creates draft reply
      - `propose_time` → bare email extracted for `attendee_email`
      - `ask_availability` → one `create_hold` per slot tagged with
        `message.thread_id`; `find_open_slots` called with `now=now`;
        `draft_slot_offer` gets the full slot list
      - `ask_availability` with zero open slots → no holds created,
        still drafts with an empty list
      - `accept_slot` → `confirm_hold` called as
        `(cal_service, message.thread_id, hold.id)`; drafts
        confirmation; creates draft reply
      - `run_cycle` processes every unread ID once, reusing the same
        `now`/`tz_name` across all of them
      - `run_cycle` computes `now` from `get_calendar_timezone` +
        `ZoneInfo`
      - `run_cycle` with zero unread messages → `process_message`
        never called
      - `main()` wires real service/client factories into `run_cycle`
      - 90/90 tests pass, `mypy .` and `ruff check .`/`ruff format --check .`
        all clean
- [x] Integration test: not needed as a separate test —
      `process_message` and `run_cycle`'s unit tests already exercise
      the full dispatch path end to end (with collaborators mocked at
      the boundary); no real-API integration test added (see spec's
      "Out of scope" — manual verification stays with the existing
      `check_*.py` scripts pattern).
