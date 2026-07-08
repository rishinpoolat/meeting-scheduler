# Plan: Claude Email Classification + Reply Drafting

**Status:** Approved
**Spec:** see ../spec.md
**Branch:** feature/llm-classify-draft

## To Do

(none remaining)

## In Progress

(none)

## Completed

- [x] `requirements.txt`: added `anthropic>=0.40`, `python-dotenv>=1.0`
- [x] `config.py` (root): `load_dotenv()`, `ANTHROPIC_API_KEY`, `CLAUDE_MODEL`
- [x] `.env.example`: documents `ANTHROPIC_API_KEY`, `CLAUDE_MODEL`
- [x] `gmail/read.py`: `get_message_body`, `_find_plain_text`,
      `_decode_body_data`, `_is_attachment` (added after code review —
      skips `Content-Disposition: attachment` text/plain parts so a
      `.txt` attachment ahead of the real body isn't mistaken for it)
- [x] `llm/__init__.py` (empty), `llm/client.py`: `get_client()`
- [x] `llm/classify.py`: `Classification` dataclass, `classify_email()`,
      tool schema, response-boundary handling (raise vs. downgrade).
      `_parse_proposed_time` normalizes a `Z` UTC suffix before calling
      `datetime.fromisoformat` (added after code review — `fromisoformat`
      only gained native `Z` support in Python 3.11, and this project
      targets 3.10, so a `Z`-suffixed response would otherwise silently
      downgrade to `irrelevant`)
- [x] `llm/draft.py`: four `draft_*` functions, `_greeting_name`,
      `_complete` helpers
- [x] `check_llm.py`: manual smoke-test script
- [x] Unit tests (76 cases total across the full suite):
  - `tests/test_gmail_read.py` (extended): single-part plain text;
    multipart/mixed preferring plain text over an attachment; **skips a
    `text/plain` part marked `Content-Disposition: attachment` in favor
    of the real body (added after code review)**; nested
    multipart/alternative preferring plain over html; empty string for
    html-only; unpadded base64url decoding; requests `format="full"`;
    payload with no body and no parts
  - `tests/test_llm_classify.py` (new): propose_time parses datetime;
    **propose_time parses a `Z`-suffixed datetime (added after code
    review)**; ask_availability; accept_slot maps index to the correct
    `candidate_holds` entry; irrelevant; downgrades out-of-range slot
    index to irrelevant; downgrades unparseable proposed_time to
    irrelevant; downgrades naive proposed_time to irrelevant; raises
    `ValueError` when no tool_use block returned; raises `ValueError`
    for a naive `now`; prompt includes numbered candidate holds; call
    uses forced `tool_choice` + correct model
  - `tests/test_llm_draft.py` (new): each of the four functions
    includes its outcome-specific data in the prompt; each uses
    `CLAUDE_MODEL` and strips response text; each raises `ValueError`
    on empty response content; `_greeting_name` parses a display name
    and a bare email address
- [x] Integration test: skipped — `check_llm.py` is the manual
      substitute (needs a live `ANTHROPIC_API_KEY`), mirroring
      `check_gcalendar.py`'s precedent for external-API-dependent
      verification.
- [x] `CODEBASE_MAP.md` updated (`llm/`, `config.py` flipped from
      PLANNED to built)
- [x] `ruff check .` / `ruff format --check .` / `mypy .`: clean
- [x] test-runner: 76/76 pass
- [x] code-reviewer: 1 blocker + 2 moderate findings, both fixed (see
      above); 2 minor/nit findings not addressed (see spec Decision 9)
