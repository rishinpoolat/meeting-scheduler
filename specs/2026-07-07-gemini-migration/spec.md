# Spec: Migrate llm/ from Anthropic (Claude) to Google Gemini

**Status:** Approved
**Created:** 2026-07-07

## What it does

Replaces the Anthropic/Claude backend of `llm/` with Google Gemini.
Public interfaces stay the same (`llm.client.get_client()`,
`classify_email()`, the four `draft_*()` functions) so `check_llm.py`
needs no changes beyond doc wording — only the internals of
`llm/client.py`, `llm/classify.py`, `llm/draft.py`, plus
`config.py`/`requirements.txt`/`.env.example`, change.

## Decisions

1. **SDK**: `google-genai` (`from google import genai`,
   `from google.genai import types`). Drop `anthropic` entirely from
   `requirements.txt`; add `google-genai>=1.0` and `pydantic>=2.0`
   (used directly for the classification response schema, not just a
   transitive dependency).
2. **Model**: `config.GEMINI_MODEL` defaults to `"gemini-2.5-flash"`,
   overridable via a `GEMINI_MODEL` env var — same shared-constant
   pattern as before (one model for both classification and drafting).
3. **`config.py`**: `GEMINI_API_KEY` replaces `ANTHROPIC_API_KEY`
   (same lazy-validation pattern — checked only inside
   `llm.client.get_client()`, not at import time, so importing
   `llm.classify`/`llm.draft` never crashes in a keyless environment
   like CI).
4. **`llm/client.py`**: `get_client() -> Any` returns
   `genai.Client(api_key=GEMINI_API_KEY)`, raising `RuntimeError` if
   the key is missing. Same shape as before, different SDK.
5. **`llm/classify.py` — structured output, not function calling**:
   a `ClassificationResult(BaseModel)` (fields: `intent` as the same
   4-way `Literal`, `proposed_time: str | None`,
   `accepted_slot_index: int | None`) is passed as `response_schema`
   with `response_mime_type="application/json"` on
   `GenerateContentConfig`. The call reads `response.parsed` — a typed
   `ClassificationResult` instance, or `None` if Gemini couldn't
   produce schema-conforming output.
6. **Response-boundary rule carries over, condition changes**:
   `response.parsed is None` → hard contract violation → raise
   `ValueError` (was: "no tool_use block" for Anthropic). An
   out-of-range `accepted_slot_index`, or an unparseable/naive
   `proposed_time` when `intent == "propose_time"` → still downgrades
   to `Classification(intent="irrelevant", ...)`, never raises — this
   rule (raise on structural violation, downgrade on semantic
   fuzziness) is unchanged from the Anthropic version, just re-pointed
   at Gemini's response shape. The `Z`-suffix-normalization fix from
   the original code review still applies (`_parse_proposed_time`
   still does `.replace("Z", "+00:00")` before `fromisoformat`).
7. **`llm/draft.py`**: `_complete(client, prompt)` calls
   `client.models.generate_content(model=GEMINI_MODEL, contents=prompt,
   config=types.GenerateContentConfig(max_output_tokens=...))` and
   returns `response.text.strip()`, raising `ValueError` if
   `response.text` is empty/`None` (same hard-contract treatment as
   before). The four outcome-specific `draft_*` functions and prompt
   content (subject + outcome data, not the original email body) are
   unchanged.
8. **Prompt wording**: `_build_prompt` in `classify.py` drops the old
   "call the {tool} tool exactly once" instruction (not applicable —
   `response_schema` mode doesn't involve a tool call); otherwise same
   content (current date/time, from/subject, body, numbered candidate
   holds).
9. **`gmail/read.py` and `gcalendar/*` are untouched** — the MIME
   body-parsing helper and calendar layer are provider-agnostic.
10. **Docs updated**: `CLAUDE.md`'s Stack line and `README.md`'s Stack
    section change from "Anthropic API (Claude, tool use)" to "Google
    Gemini API (`google-genai`, structured output)". `.env.example`
    updates `ANTHROPIC_API_KEY`/`CLAUDE_MODEL` →
    `GEMINI_API_KEY`/`GEMINI_MODEL`, with a comment pointing at Google
    AI Studio for the free key. `check_llm.py`'s docstring wording
    updates from "Anthropic API" to "Gemini API"; no functional changes
    needed there since it only calls the stable public interface.

## Open questions

None — all resolved above.

## Out of scope

- Any dual-provider / pluggable-backend abstraction — this is a full
  replacement, not an added option.
- Changing `gmail/`, `gcalendar/`, or their tests.
- Re-litigating the raise-vs-downgrade response-boundary philosophy —
  only its Gemini-specific trigger condition changes.

## Affected areas

Modified:
- `llm/client.py`, `llm/classify.py`, `llm/draft.py`
- `config.py`, `requirements.txt`, `.env.example`
- `check_llm.py` (docstring only)
- `CLAUDE.md`, `README.md`
- `tests/test_llm_classify.py`, `tests/test_llm_draft.py` (rewritten to
  mock the Gemini response shape — `response.parsed` / `response.text`
  — instead of Anthropic's `response.content` blocks)

Unaffected:
- `gmail/`, `gcalendar/`, `tests/test_gmail_*`, `tests/test_gcalendar_*`

Trailing:
- `specs/ROADMAP.md` / `specs/INDEX.md` — short note that Feature 4's
  `llm/` backend was migrated to Gemini (not a new roadmap item — this
  supersedes an implementation detail of an already-shipped feature,
  not a new capability).
