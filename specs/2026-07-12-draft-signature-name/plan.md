# Plan: Drafted reply signature name

**Status:** Approved
**Spec:** see ../spec.md
**Branch:** fix/draft-signature-name

## To Do

(empty — everything below is implemented)

## In Progress

Implementation done, quality gate passed. Awaiting the developer's
explicit pre-commit approval (per testing skill) before this moves to
Completed and gets committed.

- [x] Add `gmail.settings.basic` to `auth/google_auth.py`'s `SCOPES`
- [x] `gmail/profile.py` (new): `get_display_name(service) -> str`
- [x] Thread `your_name: str` through `llm/draft.py`'s four public
      functions and `_intro()`
- [x] Wire `get_display_name()` into `agent.py:run_cycle`, threaded
      through `process_message` and each `_handle_*` helper
- [x] Manual check in `scripts/check_gmail.py` (and `check_llm.py`,
      which also needed updating for the new `your_name` param)
- [x] Unit tests:
  - `tests/test_gmail_profile.py` (new): isPrimary + displayName happy
    path; empty-displayName falls back to local part of sendAsEmail;
    missing isPrimary entry raises `ValueError`
  - `tests/test_llm_draft.py`: `your_name` threaded into all 4
    `DRAFT_CASES`; prompt contains the name
  - `tests/test_agent.py`: every `process_message(...)` call updated
    for the new trailing arg; `TestRunCycle` gets a `get_display_name`
    patch + a test asserting it's fetched once and threaded like
    `tz_name`
- [x] Integration test: not needed — existing `test_agent.py` unit
      tests already cover `run_cycle`/`process_message` threading
      end-to-end at the mock boundary; real end-to-end is covered by
      the manual verification step below instead.
- [x] Update `CODEBASE_MAP.md` (`gmail/`, `auth/`, `llm/`, `agent.py`
      sections)

**Quality gate (per testing skill):**
- test-runner: 107 passed, `mypy .` clean, `ruff check .` clean,
  `ruff format --check .` clean.
- code-reviewer: no blockers. Confirmed correctness of the threading
  chain, minimal-scope justification for `gmail.settings.basic`, and
  that the new tests genuinely exercise the fallback/raise branches
  rather than just the happy path.

**Still open:** live verification against the real account (delete
`token.json`, re-consent with the new scope, confirm a real drafted
reply signs off correctly) — not yet run, needs the developer's
interactive OAuth consent.

## Completed

(moved here once the developer has given explicit pre-commit approval)
