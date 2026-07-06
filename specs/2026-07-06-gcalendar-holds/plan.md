# Plan: Google Calendar read/write with tentative holds (`gcalendar/`)

**Status:** Approved
**Spec:** see ../spec.md
**Branch:** feature/gcalendar-holds

## To Do

(none remaining)

## In Progress

(none)

## Completed

- [x] `gcalendar/client.py` — `CALENDAR_ID = "primary"`, `get_service()`
- [x] `gcalendar/freebusy.py` — `get_calendar_timezone()`, `query_busy_intervals()` (sort/merge busy periods), `is_slot_free()`
- [x] `gcalendar/slots.py` — `TimeSlot` dataclass, `find_open_slots()` via a single `freebusy().query()` call spanning up to 5 business-day windows, subtracting busy intervals and chunking the remainder into 30-min slots
- [x] `gcalendar/events.py` — `Hold` dataclass, `book_event()`, `create_hold()` (tagged via `extendedProperties.private`), `list_holds()`, `confirm_hold()` (patch target + delete siblings), `expire_stale_holds()` (48h sweep by native `created` timestamp) — all writes pass `sendUpdates="none"`; sibling/sweep deletes swallow 404s
- [x] `check_gcalendar.py` manual E2E script
- [x] Unit tests (39 cases across 3 files):
  - `test_gcalendar_freebusy.py`: timezone lookup, request-body construction, busy-period parsing, sort/merge of overlapping periods, `is_slot_free` true/false
  - `test_gcalendar_slots.py`: fully-free calendar, weekend skip (Friday afternoon → Monday), mid-morning rounding, busy interval mid-window, fully-busy day skip, after-5pm exclusion, fully-busy lookahead window, single-freebusy-call assertion, **naive-`now` raises `ValueError`** (added after code review)
  - `test_gcalendar_events.py`: `book_event`/`create_hold` request bodies + `sendUpdates="none"`, `list_holds` filter construction (with/without thread_id) + timestamp parsing, `confirm_hold` sibling deletion + no-siblings case + 404-swallow, `expire_stale_holds` cutoff filtering + empty case + 404-swallow
- [x] Integration test: skipped — needs a live Calendar account. `check_gcalendar.py` is the manual substitute; developer will run it once this lands.
- [x] `CODEBASE_MAP.md` updated — `gcalendar/` flipped from PLANNED to built
- [x] `ruff check` / `ruff format` / `mypy .`: clean
- [x] test-runner: 39/39 pass, mypy clean, ruff clean, no regressions in existing `gmail`/`auth` suites
- [x] code-reviewer: no blockers. Two minor findings fixed (naive-`now` guard in `find_open_slots` + warning comment on `check_gcalendar.py`'s unscoped sweep — see spec.md Decision 13). One nit left as a note for the live manual run (PATCH merge semantics on `extendedProperties.private` — untestable via mocks).
