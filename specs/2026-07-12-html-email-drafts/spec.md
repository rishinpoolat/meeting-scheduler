# Spec: HTML-formatted drafted replies

**Status:** Approved
**Created:** 2026-07-12

## What it does

Drafted replies gain a rich HTML alternative (bold meeting times,
boxed layout for offered slots) alongside the existing plain-text
body, instead of plain text only.

## Decisions

- New `DraftBody(text: str, html: str)` dataclass in `llm/draft.py`;
  all four `draft_*` functions return it instead of `str`.
- One Gemini call per function (unchanged) — a single plain-text
  template is deterministically turned into both `text` and `html`
  in Python, rather than asking Gemini for two completions (would
  double free-tier quota usage for no benefit).
- Gemini is instructed to write plain prose only, no markdown — this
  project's established rule is to never trust LLM free text for
  anything structural (see
  `specs/2026-07-12-verbatim-meeting-times/spec.md`).
- Critical fix found during design review: the placeholder must
  occupy its own paragraph (not just "occur exactly once anywhere"),
  or substituting a block-level HTML box mid-sentence produces
  invalid, silently-reflowed HTML. Prompts reworded to require this;
  verification changed to paragraph-exact-match, raising `ValueError`
  (safe retry-next-run) if violated.
- HTML derivation: split template into paragraphs on blank lines;
  non-placeholder paragraphs are escaped and wrapped in `<p>`
  (internal `\n` → `<br>`); the placeholder paragraph is replaced with
  a deterministic HTML box built directly from the datetime objects
  already in scope (never by parsing the plain-text value back
  apart).
- Box styling: inline styles only, light bordered box, bold date,
  muted time — targets modern clients (Gmail, Apple Mail); the
  always-present plain-text alternative is the fallback for anything
  else. Multi-slot case reuses the same box as table rows.
- `gmail/draft.py`'s `create_draft_reply` takes a `DraftBody` and
  builds a standard `multipart/alternative` MIME message
  (`set_content` + `add_alternative(..., subtype="html")`) — first
  time `gmail/` imports a type from `llm/` (previously only the
  reverse); confirmed no import cycle.
- `agent.py` needs no changes (confirmed by tracing every call site).

## Open questions

None — resolved via a Plan-agent design review before implementation,
which also found and specified the fix for the paragraph-nesting bug
above.

## Out of scope

- No markdown parsing/rendering.
- No Outlook-desktop-specific HTML hardening beyond the table-based
  multi-slot layout.
- No user-configurable styling/theming.

## Affected areas

- `llm/draft.py`, `gmail/draft.py`
- `scripts/check_gmail.py`, `scripts/check_llm.py`
- `tests/test_llm_draft.py`, `tests/test_gmail_draft.py`
- `CODEBASE_MAP.md`
