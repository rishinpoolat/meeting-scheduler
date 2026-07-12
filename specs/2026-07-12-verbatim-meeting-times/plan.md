# Plan: Drafted meeting times can be silently corrupted by Gemini

**Status:** Approved
**Spec:** see ../spec.md
**Branch:** fix/verbatim-meeting-times

## To Do

(empty — everything implemented)

## In Progress

Implementation done, quality gate passed twice (initial + a
follow-up fix from review). Awaiting the developer's explicit
pre-commit approval before this moves to Completed.

## Completed (pending commit)

- [x] `llm/draft.py`: placeholder constants, `_format_date`/
      `_format_time`/`_format_range` rewritten to produce a friendly
      12-hour phrase in pure Python, `_complete_with_placeholder()`
      raising `ValueError` on missing OR duplicated placeholder
      (`text.count(placeholder) != 1`, tightened after review — a
      duplicate would otherwise leak a literal placeholder into the
      drafted email)
- [x] Rewrote `draft_booking_confirmation`, `draft_time_unavailable`,
      `draft_slot_confirmed`, `draft_slot_offer` (incl. empty-slots
      branch) to use the placeholder pattern; signatures unchanged,
      `agent.py` needed no changes
- [x] Already applied, folded into this commit: `_intro()`'s "Best,"
      closing-line instruction fix
- [x] Unit tests: pure-function format tests, regression test pinning
      the exact previously-corrupted case, placeholder-substitution
      tests, empty-slots test, missing-placeholder AND
      duplicated-placeholder `ValueError` tests, updated existing
      generic parametrized tests for placeholder-aware mocks
- [x] Integration test: not needed, as scoped — unit tests cover the
      full path per function; `agent.py` unchanged
- [x] Updated `CODEBASE_MAP.md` (`llm/` section: documents the
      verify-then-substitute pattern)

**Quality gate (per testing skill), two rounds:**
- Round 1 — test-runner: 142 passed, mypy/ruff clean. code-reviewer:
  found one real gap (presence-only check, not exact-once) that could
  let a duplicated placeholder leak into a drafted email.
- Round 2 (after fixing the gap) — test-runner: 146 passed, mypy/ruff
  clean. code-reviewer: confirmed the fix is correct and sufficient
  (`str.count`/`str.replace` non-overlapping semantics agree, no
  remaining edge case), confirmed the new test exercises the real bug
  scenario through the public function, no blockers.

**Still open:** live end-to-end verification against the real Gemini
API is blocked by the free tier's exhausted daily quota (20
requests/day) — deferred as a follow-up once it resets, alongside the
already-noted manual OAuth/display-name verification from
`specs/2026-07-12-draft-signature-name/plan.md`.
