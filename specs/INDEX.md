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
