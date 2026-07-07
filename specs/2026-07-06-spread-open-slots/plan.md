# Plan: Spread open slots across morning/afternoon

**Status:** Approved
**Spec:** see ../spec.md
**Branch:** feature/spread-open-slots

## To Do

(none remaining)

## In Progress

(none)

## Completed

- [x] `gcalendar/slots.py`: added `MIDDAY_SPLIT_HOUR = 13`; replaced `_business_hour_windows` with `_half_day_windows`; replaced `_chunk_into_slots` with `_first_slot_in_window`; updated `find_open_slots` loop (checks count before processing each window, explicit `count <= 0` early return)
- [x] `tests/test_gcalendar_slots.py`: rewritten scenario list (15 cases) — fully-free spread across 3 half-days, mid-morning/mid-afternoon rounding, exactly-13:00 boundary, exactly-17:00 boundary (added after code review), after-5pm exclusion, Friday-afternoon-to-Monday-morning regression test, busy-morning-skip-to-afternoon, partial-busy-block-shift, fully-busy-day skip, fully-busy-lookahead returns fewer, single-freebusy-call, naive-`now` raises, `count=0` and `count=-1` both return `[]`
- [x] `CODEBASE_MAP.md`: `slots.py` description updated to mention half-day spread
- [x] `ruff check` / `ruff format` / `mypy .`: clean
- [x] test-runner: 45/45 pass, mypy clean, ruff clean, no regressions
- [x] code-reviewer: no blockers. Hand-traced all boundary cases (13:00 split, 17:00 edge, weekend skip) — correct. Two minor test-coverage nits (exact 17:00 boundary, negative `count`) both added as tests.
- [x] Developer manually confirmed the original clustering behavior via `check_gcalendar.py` before this fix (motivated the feature)
