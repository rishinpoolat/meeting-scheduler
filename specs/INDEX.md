# Specs Index

> One-line log of **completed** features. Read this instead of opening
> every `specs/*/spec.md` — it costs far less context. Only open a
> specific feature's `spec.md`/`plan.md` when working directly on or
> near that area. See [`specs/ROADMAP.md`](./ROADMAP.md) for what's
> planned next. This file is shared/directly-editable (like
> `CODEBASE_MAP.md`), not owned by a single feature branch.

- **2026-07-06 — google-oauth**: OAuth2 for Gmail + Calendar.
  `auth/google_auth.py`'s `get_credentials()` caches/refreshes a token,
  falls back to interactive consent when missing/corrupt/unrefreshable.
  → [`specs/2026-07-06-google-oauth/`](./2026-07-06-google-oauth/)

- **2026-07-06 — gmail-read-draft**: List unread inbox messages (no
  relevance filtering — deferred to Claude classification) and create
  correctly threaded Gmail draft replies. `gmail/{client,read,draft}.py`.
  → [`specs/2026-07-06-gmail-read-draft/`](./2026-07-06-gmail-read-draft/)

- **2026-07-06 — gcalendar-holds**: Calendar free/busy checks, open-slot
  finding (5 slots across the next 5 business days via a single
  freebusy query), confirmed event booking, and the tentative-hold
  mechanism (create tagged with a Gmail thread ID via
  `extendedProperties.private`, confirm-and-release-siblings,
  48-hour stale-hold sweep). `gcalendar/{client,freebusy,slots,events}.py`.
  → [`specs/2026-07-06-gcalendar-holds/`](./2026-07-06-gcalendar-holds/)

- **2026-07-07 — llm-classify-draft**: Claude tool-use email classification
  (intent + proposed datetime + thread-hold-acceptance matching, with a
  raise-vs-downgrade rule for malformed model responses) and four
  outcome-specific reply-drafting functions. Also adds
  `gmail.read.get_message_body()` (full MIME body fetch, since only a
  short snippet was available before) and root `config.py`/`.env` for
  the Anthropic API key. `llm/{client,classify,draft}.py`, `config.py`.
  → [`specs/2026-07-07-llm-classify-draft/`](./2026-07-07-llm-classify-draft/)

- **2026-07-07 — gemini-migration**: Swapped `llm/`'s backend from
  Anthropic (Claude) to Google Gemini (`google-genai`, free tier).
  `classify_email()` now uses Gemini structured output
  (`response_schema` + a Pydantic model) instead of forced tool-use;
  the raise-vs-downgrade response-boundary rule and reply-drafting
  interface are unchanged, just re-pointed at Gemini's response shape.
  `config.py` now reads `GEMINI_API_KEY`/`GEMINI_MODEL`.
  → [`specs/2026-07-07-gemini-migration/`](./2026-07-07-gemini-migration/)

- **2026-07-09 — agent-orchestration**: `agent.py` wires Features 1–4
  together into one polling cycle — for every unread message, fetches
  the thread's existing holds, classifies intent, then books/offers
  slots/confirms a hold/skips accordingly, and creates a Gmail draft
  reply. `agent.py`.
  → [`specs/2026-07-09-agent-orchestration/`](./2026-07-09-agent-orchestration/)

- **2026-07-09 — polling-loop**: Idempotency + basic error logging for
  `agent.py`, descoped from an originally-planned scheduling loop — the
  developer chose to keep `agent.py` a manually-run, single-pass
  script instead. Each run now sweeps holds older than 48h
  (`gcalendar.events.expire_stale_holds()`), marks every processed
  message read via new `gmail.read.mark_as_read()` (including
  `irrelevant` ones, so spam isn't reclassified on the next run), and
  isolates per-message failures (logged with the message ID, left
  unread to retry) instead of aborting the whole run. `agent.py`,
  `gmail/read.py`.
  → [`specs/2026-07-09-polling-loop/`](./2026-07-09-polling-loop/)

- **2026-07-12 — draft-signature-name**: Drafted replies sign off with
  the account's real Gmail display name (`gmail/profile.py`'s
  `get_display_name()`, via `sendAs.list`'s `isPrimary` entry, needing
  the new `gmail.settings.basic` scope) instead of a `[Your Name]`
  placeholder. Also caps `agent.py`'s per-run unread polling by both a
  2-day window and a 5-message count, to stay under Gemini's free-tier
  rate limit. `gmail/profile.py`, `auth/google_auth.py`, `agent.py`,
  `gmail/read.py`.
  → [`specs/2026-07-12-draft-signature-name/`](./2026-07-12-draft-signature-name/)

- **2026-07-12 — earliest-offer-time**: `ask_availability` now
  respects a sender-stated timeframe preference (e.g. "next week") via
  a new `earliest_offer_time` field on `Classification`, threaded into
  `gcalendar.slots.find_open_slots()`'s new `earliest` param
  (clamped to never precede `now`). A malformed value falls back to
  `None` rather than downgrading the whole classification, unlike
  `proposed_time`/`accepted_slot_index` — deliberate asymmetry, see
  spec. Also disables Gemini's "thinking" tokens
  (`thinking_budget=0`) in `llm/classify.py` and `llm/draft.py` after
  a real run hit `MAX_TOKENS` truncation. `llm/classify.py`,
  `gcalendar/slots.py`, `agent.py`.
  → [`specs/2026-07-12-earliest-offer-time/`](./2026-07-12-earliest-offer-time/)

- **2026-07-12 — verbatim-meeting-times**: Gemini no longer writes
  meeting dates/times into drafted replies itself — a real drafted
  confirmation showed a wrong time after Gemini non-deterministically
  corrupted a correct value while reformatting it into prose. `llm/draft.py`'s
  four functions now have Gemini leave a literal placeholder
  (`[[MEETING_TIME]]`/`[[SLOT_LIST]]`) which Python substitutes with a
  guaranteed-correct, Python-formatted value, raising if the
  placeholder is missing or duplicated. `llm/draft.py`.
  → [`specs/2026-07-12-verbatim-meeting-times/`](./2026-07-12-verbatim-meeting-times/)

- **2026-07-12 — html-email-drafts**: Drafted replies are now sent as
  `multipart/alternative` (plain text + HTML), not plain text only.
  `llm/draft.py`'s four drafting functions return a new
  `DraftBody(text, html)` dataclass instead of a plain string; Gemini
  leaves the meeting-time/slot-list placeholder alone on its own
  paragraph, and `_complete_with_placeholder()` now requires both a
  single isolated-paragraph match *and* a single total substring
  occurrence (a review-caught gap: a mid-sentence duplicate alongside
  one correctly isolated copy previously slipped through and could leak
  the literal placeholder into a real draft) before deriving an
  HTML-escaped `<p>`/`<br>` version and substituting a Python-built,
  inline-styled HTML box for the placeholder paragraph.
  `gmail/draft.py`'s `create_draft_reply()` sends both parts via
  `set_content` + `add_alternative(subtype="html")`.
  `llm/draft.py`, `gmail/draft.py`.
  → [`specs/2026-07-12-html-email-drafts/`](./2026-07-12-html-email-drafts/)
