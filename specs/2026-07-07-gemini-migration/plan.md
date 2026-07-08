# Plan: Migrate llm/ from Anthropic (Claude) to Google Gemini

**Status:** Approved
**Spec:** see ../spec.md
**Branch:** feature/gemini-migration

## To Do

(none remaining)

## In Progress

(none)

## Completed

- [x] `requirements.txt`: removed `anthropic`, added `google-genai>=1.0`,
      `pydantic>=2.0`
- [x] `config.py`: `GEMINI_API_KEY`, `GEMINI_MODEL` (default
      `"gemini-2.5-flash"`) replacing the Anthropic constants
- [x] `.env.example`: `GEMINI_API_KEY`/`GEMINI_MODEL`, note pointing to
      Google AI Studio
- [x] `llm/client.py`: `get_client()` returns `genai.Client(...)`
- [x] `llm/classify.py`: `ClassificationResult` Pydantic model,
      `classify_email()` rebuilt on `response_schema`/`response.parsed`,
      response-boundary rule re-pointed (`parsed is None` → raise),
      downgrade logic and `Z`-suffix fix preserved, prompt's
      tool-calling instruction removed
- [x] `llm/draft.py`: `_complete()` rebuilt on
      `generate_content(...).text`; four `draft_*` functions otherwise
      unchanged
- [x] `check_llm.py`: docstring wording only ("Anthropic" → "Gemini")
- [x] `CLAUDE.md`, `README.md`: Stack line/section updated (README's
      Status section and Commands table also fixed to mention `llm/`
      and `check_llm.py`, which a prior feature had left stale)
- [x] `CODEBASE_MAP.md`: `llm/` and `config.py` sections updated to
      describe the Gemini internals (added after code review — this
      was missing from the original To Do list and left the doc
      factually wrong, e.g. still saying `config.ANTHROPIC_API_KEY`)
- [x] Rewrote `tests/test_llm_classify.py` and `tests/test_llm_draft.py`
      mocking helpers for the Gemini response shape, keeping the same
      case coverage as before (all raise/downgrade branches, prompt
      content assertions, model/config kwargs assertions) plus the
      existing `Z`-suffix regression case. `_client_with_empty_text`
      uses `response.text = None` (not `""`) after code review, to
      match the real SDK's actual no-content behavior.
- [x] `specs/ROADMAP.md` / `specs/INDEX.md`: short note on the backend
      migration
- [x] Integration test: skipped — `check_llm.py` remains the manual
      substitute (now needs a live `GEMINI_API_KEY` instead)
- [x] `ruff check .` / `ruff format --check .` / `mypy .`: clean
- [x] test-runner: 78/78 pass
- [x] code-reviewer: 1 blocker (`CODEBASE_MAP.md` left stale), fixed;
      1 test-fidelity nit (`""` vs `None`), fixed; verified via reading
      the installed `google-genai` SDK source that `response.parsed is
      None` and `response.text` falsy both correctly cover all Gemini
      failure modes (safety blocks, truncated JSON, schema mismatch);
      1 remaining nit (now-redundant `isinstance` defensive checks in
      `classify.py`) deliberately left as-is — harmless, and still a
      reasonable defensive check at an external API boundary
