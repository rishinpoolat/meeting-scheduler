# Spec: Read unread Gmail messages + create a draft reply

**Status:** Approved
**Created:** 2026-07-06

## What it does

Lists unread inbox messages (capped at 50) and can create a Gmail
draft that replies correctly (threaded, right subject, right
recipient) to any one of them, using a hardcoded placeholder body for
now.

## Decisions

- **No sender/address filtering in this feature.** List *all* unread
  inbox messages (`labelIds=["INBOX","UNREAD"]`, `maxResults=50`).
  Deciding which of those 50 are actually meeting enquiries vs.
  newsletters/spam is Claude's job (Feature 4) — hard-coding a contact
  address filter here would be fragile and duplicate that logic.
- `list_unread_message_ids()` — one `messages.list` call, returns just
  message IDs (`list[str]`). Cheap; matches the 50-cap decision from
  the roadmap. Deliberately not returning `threadId` here — nothing
  consumes it at this step, since `get_message()` re-fetches it as
  part of building the `Message` object anyway. (Revised from the
  original plan's `(id, threadId)` pairs after implementation showed
  the tuple was never actually used.)
- `get_message(message_id)` — one `messages.get` call per message,
  `format="metadata"` with `metadataHeaders=["From","Subject",
  "Message-Id","References"]`. Returns a small `Message` object:
  `id`, `thread_id`, `subject`, `from_address`, `message_id_header`,
  `references_header`, `snippet`. Deliberately **not** parsing the full
  MIME body yet — nothing needs it until Feature 4 (Claude
  classification), and multipart body-parsing is real complexity not
  worth adding before it's needed.
- `create_draft_reply(message, body_text)` — builds the reply with
  Python's stdlib `email.message.EmailMessage` (no new dependency):
  `To` = original sender, `Subject` = original subject with `"Re: "`
  prefixed only if not already present, `In-Reply-To` = original
  `Message-Id` header, `References` = original `References` header
  (if any) + original `Message-Id`, body = the given text. Sets
  `threadId` on the draft request so Gmail threads it under the
  original conversation. Base64url-encodes the raw MIME, calls
  `drafts().create()`.
- Module layout: `gmail/client.py` (builds the Gmail API service from
  `auth.google_auth.get_credentials()`), `gmail/read.py` (list/get),
  `gmail/draft.py` (create_draft_reply).
- Placeholder body text lives as a constant used only by the manual
  verification script — not meant to be final content (Feature 4
  replaces it with Claude-generated text).

## Open questions

(none — resolved above)

## Out of scope

- Sender/relevance filtering
- Full email body parsing
- Calendar involvement
- Claude involvement
- Marking messages read/processed (still Feature 6's job)

All of the above are later features.

## Affected areas

- `gmail/` (new package)
- `check_gmail.py` (new, manual verification script)
- `tests/test_gmail_read.py`, `tests/test_gmail_draft.py` (new)
- `CODEBASE_MAP.md` — `gmail/` entry flips from PLANNED to built
