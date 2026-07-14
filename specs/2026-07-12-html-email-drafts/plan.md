# Plan: HTML-formatted drafted replies

**Status:** Approved
**Spec:** see ../spec.md
**Branch:** feature/html-email-drafts

## To Do

(none — all items completed, see below)

## In Progress

(none)

## Completed

- [x] `llm/draft.py`: `DraftBody` dataclass; reword the three
      single-time prompts to require the placeholder alone on its own
      paragraph line; change verification to paragraph-exact-match
      (raise `ValueError` otherwise); HTML derivation (escape +
      paragraph→`<p>`/`<br>` + deterministic box substitution); no-markdown
      instruction added to `_intro()`; box/table HTML builder functions
- [x] `gmail/draft.py`: `create_draft_reply` takes `DraftBody`, builds
      `multipart/alternative` via `set_content` + `add_alternative`
- [x] `scripts/check_gmail.py`: `PLACEHOLDER_BODY` → `DraftBody`
- [x] `scripts/check_llm.py`: print `.text`, write `.html` to a temp
      file and open it via `webbrowser.open`
- [x] Unit tests:
  - `tests/test_llm_draft.py`: update every mocked fixture placing the
    placeholder mid-sentence to its own paragraph; `result == "..."`
    → `result.text == "..."`; new tests for placeholder-not-alone
    raises, HTML escaping, paragraph/`<br>` conversion, and
    placeholder-absent-from-html per success case
  - `tests/test_gmail_draft.py`: `DraftBody` args;
    `mime.get_body(preferencelist=(...))` assertions for both parts
  - `tests/test_agent.py`: no changes needed (confirmed — every
    `create_draft_reply` touchpoint is mocked)
- [x] Integration test: not needed — unit tests cover the full
      derivation path per function; manual visual check via
      `scripts/check_llm.py` covers real rendering.
- [x] Update `CODEBASE_MAP.md` (`gmail/`, `llm/` sections)
- [x] Post-review fix: `_complete_with_placeholder`'s duplication check
      also requires the total substring count to be 1, not just the
      paragraph-exact-match count — a mid-sentence duplicate alongside
      one correctly isolated copy previously slipped through and would
      have leaked the literal placeholder token into a real draft.
      Added `test_draft_functions_raise_value_error_when_placeholder_duplicated_mid_sentence`
      to cover it. Found by code-reviewer, verified, fixed.

test-runner: 161 passed, mypy clean, ruff clean.
code-reviewer: one blocker found (duplication-check gap above) and
fixed; no other issues.
Developer pre-commit approval: given.

Merged: commit `1b4f9e1`, PR #9, merged to `main` at `f9837cc`.
