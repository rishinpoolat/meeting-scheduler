# Plan: Drafted meeting times can be silently corrupted by Gemini

**Status:** Approved
**Spec:** see ../spec.md
**Branch:** fix/verbatim-meeting-times

## To Do

(empty — everything implemented)

## In Progress

(empty)

## Completed

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

**Committed:** 2026-07-12, `fix/verbatim-meeting-times` commit
`1f0d0bb` (also folded in an unrelated one-line `config.py` fix found
during this session: `GEMINI_MODEL`'s default had been changed to
`"gemini-3.5-flash"`, which was assumed to be a typo and reverted to
`"gemini-2.5-flash"` — **this assumption turned out to be wrong**, see
correction below).

**Merged:** 2026-07-12 to `main` via PR #8, merge commit `6e1b483`.

**Correction (2026-07-12, post-merge hotfix, direct to `main`):** the
`gemini-3.5-flash` → `gemini-2.5-flash` revert above was itself
mistaken — `gemini-3.5-flash` is a real model the developer's account
has access to (confirmed via `client.models.list()`), and
`gemini-2.5-flash` had actually been sunset for new accounts
(`404 NOT_FOUND: "This model models/gemini-2.5-flash is no longer
available to new users"`, hit live during real testing after the
merge). `config.py`'s default changed again, this time to
`gemini-flash-latest` (an alias that always resolves to Google's
current recommended flash model, chosen over re-pinning to
`gemini-3.5-flash` specifically to avoid a third deprecation
scramble) — confirmed working via a live `generate_content` call.
Hardcoded `"gemini-2.5-flash"` mentions in code comments
(`llm/classify.py`, `llm/draft.py`, `scripts/check_llm.py`) were also
generalized to not name a specific model version.

**Still open:** live end-to-end verification against the real Gemini
API is blocked by the free tier's exhausted daily quota (20
requests/day) — deferred as a follow-up once it resets, alongside the
already-noted manual OAuth/display-name verification from
`specs/2026-07-12-draft-signature-name/plan.md`.
