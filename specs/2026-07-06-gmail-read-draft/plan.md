# Plan: Read unread Gmail messages + create a draft reply

**Status:** Approved
**Spec:** see ../spec.md
**Branch:** feature/gmail-read-draft

## To Do

(none remaining)

## In Progress

(none)

## Completed

- [x] `gmail/__init__.py`, `gmail/client.py` — `get_service()`
- [x] `gmail/read.py` — `Message` dataclass, `list_unread_message_ids()`,
      `get_message()`
- [x] `gmail/draft.py` — `create_draft_reply()`
- [x] `check_gmail.py` — manual verification script
- [x] Unit tests (13/13 passing, including 5 pre-existing auth tests):
  - `list_unread_message_ids` calls `messages.list` with the right
    query/cap, handles no-unread-messages case
  - `get_message` parses headers case-insensitively, handles missing
    `References`
  - `create_draft_reply` builds correct To/Subject/In-Reply-To/
    References/threadId, doesn't double-prefix "Re:" (both exact-case
    and case-insensitive variants), handles no prior References,
    asserts actual decoded MIME content
- [x] Integration test: intentionally skipped, needs a real live
      Gmail inbox — `check_gmail.py` is the manual substitute (still
      pending developer's manual run).
- [x] Updated `CODEBASE_MAP.md`'s `gmail/` entry (PLANNED → built) —
      also fixed a stale PLANNED marker left on `auth/` from the prior
      feature, and flipped `tests/`.
- [x] test-runner: 13/13 pass, ruff clean, mypy clean.
- [x] code-reviewer: no blockers. Fixed: added a case-insensitive
      "RE:" test variant, removed a redundant `get_message` call in
      `check_gmail.py`. Flagged a spec deviation
      (`list_unread_message_ids` returns `list[str]` not `(id,
      threadId)` pairs) — developer confirmed keeping the simpler
      signature; spec.md updated to match.
