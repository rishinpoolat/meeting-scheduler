# Plan: Respect the sender's stated timeframe when offering availability

**Status:** Approved
**Spec:** see ../spec.md
**Branch:** fix/earliest-offer-time

## To Do

(empty — everything implemented)

## In Progress

Implementation done, quality gate passed. Awaiting the developer's
explicit pre-commit approval (per testing skill) before this moves to
Completed and gets committed.

## Completed (pending commit)

- [x] `llm/classify.py`: `ClassificationResult.earliest_offer_time`
      field, `Classification.earliest_offer_time` field, renamed
      `_parse_proposed_time` → `_parse_iso_datetime`, new
      `ask_availability` branch in `_to_classification`, added
      `earliest_offer_time=None` to the other 4 existing
      `Classification(...)` construction sites
- [x] `gcalendar/slots.py`: `earliest: datetime | None = None` param on
      `find_open_slots`, tz-aware check, `current = max(current,
      earliest...)` clamp
- [x] `agent.py`: threaded `classification.earliest_offer_time` through
      `_handle_ask_availability` into `find_open_slots`
- [x] Unit tests: 7 new in `tests/test_llm_classify.py` (parses,
      Z-suffix, unparseable/naive fall back to `None` — the asymmetry
      tests — and 3 "ignored for other intents"), 7 new in
      `tests/test_gcalendar_slots.py` (after-now, before-now clamp,
      mid-day rounding, weekend rollover, far-future full count, naive
      raises, no-arg regression smoke test), 1 new in
      `tests/test_agent.py` (threading), plus mechanical updates to
      existing `Classification(...)`/`find_open_slots` call sites
- [x] Integration test: not needed, as scoped in the plan — unit tests
      already cover the full threading path at the mock boundary
- [x] Updated `CODEBASE_MAP.md` (`llm/`, `gcalendar/`, `agent.py`
      sections)

**Quality gate (per testing skill):**
- test-runner: 132 passed, `mypy .` clean, `ruff check .` clean,
  `ruff format --check .` clean.
- code-reviewer: no blockers. Hand-verified the clamp logic's edge
  cases (weekend rollover, far-future, mid-day rounding) against
  `_half_day_windows`, confirmed the asymmetry vs. `proposed_time`'s
  downgrade rule is correctly and consistently implemented across all
  6 `Classification(...)` sites, and confirmed `agent.py` threading is
  positionally/semantically correct end to end. Two non-blocking nits:
  a line right at the 88-char boundary (confirmed fine via
  `ruff format --check`) and no explicit test for `earliest == now`
  (low risk, `max()`'s tie-breaking is inconsequential either way).
