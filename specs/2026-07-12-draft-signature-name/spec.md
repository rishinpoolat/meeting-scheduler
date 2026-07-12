# Spec: Drafted reply signature name

**Status:** Approved
**Created:** 2026-07-12

## What it does

Drafted replies currently sign off with a literal `[Your Name]`
placeholder because Gemini is never told who the account owner is.
This fix sources the account's real display name from Gmail and has
every drafted reply sign off with it.

## Decisions

- Source of the name: `users.settings.sendAs.list` (Gmail API), the
  `displayName` of the entry where `isPrimary` is true — the account's
  own configured "send mail as" name.
- New scope required: `gmail.settings.basic`, added to
  `auth/google_auth.py`'s `SCOPES`. The existing `token.json` was
  authorized under the old scope set and must be regenerated — the
  next real run triggers a fresh interactive OAuth consent screen.
- Fallback if `displayName` is empty (account never set one in Gmail
  settings): use the local part of that entry's `sendAsEmail` (before
  the `@`) — mirrors the existing `_greeting_name` fallback already in
  `llm/draft.py`.
- Fallback if no `isPrimary` entry is present at all (API contract
  violation, shouldn't happen in practice): raise `ValueError` — same
  "raise on truly malformed external response" precedent used in
  `llm/classify.py`.
- Fetched once per run, not per-message — same pattern already used
  for `now`/`tz_name` in `agent.py:run_cycle`, threaded through
  `process_message` and into the per-intent handlers.
- Gemini is told to sign with the name exactly as returned (no
  first-name-only truncation).

## Open questions

None — all resolved with the developer before implementation.

## Out of scope

- No caching of the fetched display name across runs (cheap call,
  fetched fresh every `run_cycle` in case the account's name changes).
- No config override/toggle for the name.
- No Google People API integration — Gmail's own send-as settings are
  sufficient and avoid a second API surface.

## Affected areas

- `auth/google_auth.py` (new scope)
- `gmail/profile.py` (new)
- `agent.py` (fetch + threading)
- `llm/draft.py` (new `your_name` param on all 4 draft functions)
- `scripts/check_gmail.py` (manual check)
- `tests/test_gmail_profile.py` (new), `tests/test_llm_draft.py`,
  `tests/test_agent.py`
- `CODEBASE_MAP.md`
