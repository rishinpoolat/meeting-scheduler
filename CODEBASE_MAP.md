# Codebase Map

> A table of contents for the project. Read this before exploring the
> file tree or grepping — update it whenever folder structure or key
> files change. Shared across the team — keep entries scoped to your
> own feature's area to minimize overlap with concurrent edits from
> others.

> **Nothing below except `specs/` is built yet.** Entries marked
> PLANNED describe the intended structure so features can be planned
> against it; drop the marker once each is actually built.

## agent.py (PLANNED)

Entry point. Orchestrates one polling cycle: fetch unread emails,
classify intent, act (book event or find slots), draft reply.

## auth/

OAuth2 flow (`google-auth-oauthlib`) and token storage/refresh for the
combined Gmail + Calendar scopes. `google_auth.py` exposes
`get_credentials()` — always import this rather than touching
`credentials.json`/`token.json` directly.

## gmail/

Gmail API wrapper. `client.py` builds the authenticated service via
`auth.get_credentials()`; `read.py` lists unread inbox messages and
fetches header metadata (`Message` dataclass — no body parsing yet);
`draft.py` creates threaded draft replies (`In-Reply-To`/`References`/
`threadId`). No sender/relevance filtering here by design — that's
Claude's job (planned `llm/`).

## gcalendar/

Google Calendar API wrapper. Named `gcalendar/`, not `calendar/`, to
avoid shadowing Python's stdlib `calendar` module. `client.py` builds
the authenticated service via `auth.get_credentials()` and defines
`CALENDAR_ID = "primary"`, the single calendar this project operates
against; `freebusy.py` reads the calendar's IANA timezone (off an
`events().list()` response, to avoid needing a broader scope) and
checks/queries free-busy; `slots.py` finds up to 5 open 30-minute
slots across the next 5 business days (9am-5pm), at most one per
half-day (morning 9-1, afternoon 1-5) so offered times spread out
instead of clustering, from a single `freebusy.query` call (`TimeSlot`
dataclass); `events.py` books
confirmed events, creates tentative holds tagged with a Gmail thread
ID via `extendedProperties.private` (`scheduler_hold`/
`scheduler_thread_id`), confirms a hold while deleting its siblings,
and sweeps/deletes holds older than 48 hours (`Hold` dataclass). Every
write passes `sendUpdates="none"` — this project never lets Calendar
auto-email attendees; the only outbound channel is a manually-reviewed
Gmail draft.

## llm/

Gemini-based orchestration (`google-genai` SDK). `client.py` builds the
Gemini client via `config.GEMINI_API_KEY` (validated lazily, only
inside `get_client()`, so importing the other modules never requires a
key); `classify.py`'s `classify_email()` uses structured output (a
`ClassificationResult` Pydantic model passed as `response_schema`) to
classify an email's scheduling intent (propose a specific time / ask
availability / accept one of a thread's previously-offered holds /
irrelevant) and extract a proposed datetime or matched `Hold` — a
malformed-but-well-formed response (bad index, unparseable/naive time)
downgrades to `irrelevant` rather than raising, while `response.parsed
is None` (Gemini couldn't produce schema-conforming output) raises (see
spec for the raise-vs-downgrade rule); `draft.py` has four
outcome-specific functions (not one polymorphic type) that draft reply
text via plain Gemini completions, one per calendar outcome. Pure
module — no Gmail/Calendar API calls happen here; the orchestrator
(planned `agent.py`) wires `llm/` together with `gmail/`/`gcalendar/`.

## config.py

Loads `.env` via `python-dotenv` and exposes `GEMINI_API_KEY` /
`GEMINI_MODEL` (shared by classification and drafting). Credential
paths for Google auth stay in `auth/google_auth.py`, not here.

## tests/

pytest suite; mocks the Gmail/Calendar API clients (`unittest.mock`,
no real network calls). Config in `pyproject.toml`
(`[tool.pytest.ini_options]`).

## specs/

Per-feature spec/plan folders (`specs/<date>-<name>/spec.md` +
`plan.md`), scaffolded from `specs/_TEMPLATE/`. See git-workflow skill
for file-ownership rules.

---

Last structural update: 2026-07-07 (llm/ backend migrated from
Anthropic to Gemini)
