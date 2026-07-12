# Codebase Map

> A table of contents for the project. Read this before exploring the
> file tree or grepping — update it whenever folder structure or key
> files change. Shared across the team — keep entries scoped to your
> own feature's area to minimize overlap with concurrent edits from
> others.

> **Nothing below except `specs/` is built yet.** Entries marked
> PLANNED describe the intended structure so features can be planned
> against it; drop the marker once each is actually built.

## agent.py

Entry point (`python agent.py` / `main()`) — a manually-run, **single
pass**, by design: no internal scheduling loop or polling interval
(considered and explicitly rejected). `run_cycle()` sweeps stale holds
(`gcalendar.events.expire_stale_holds()`) first, then fetches this
run's `now`/timezone (`get_calendar_timezone()` +
`datetime.now(ZoneInfo(...))`) and the account's display name
(`gmail.profile.get_display_name()`, used to sign drafted replies)
once each, lists unread messages (capped by both `UNREAD_BATCH_SIZE`
(5) and `UNREAD_WINDOW_DAYS` (2, via Gmail's `newer_than:Nd` search
operator) together — a rate-limit-driven safeguard so a burst of
unread mail within the window still can't blow through Gemini's
free-tier per-minute quota in one run), and for each
one wraps fetch + `process_message()` + `gmail.read.mark_as_read()` in
a single try/except — a failure anywhere in that sequence is logged
(via `logging.getLogger(__name__)`, first use of `logging` in this
codebase) with the message ID and leaves that message unread to retry
on the next manual run, without aborting the rest of the run.
`process_message()` unconditionally fetches
`gcalendar.events.list_holds(thread_id=message.thread_id)` *before*
classifying — this is what wires thread-hold-acceptance matching into
`llm.classify.classify_email()` — then dispatches on
`Classification.intent`: `propose_time` books if free (else drafts
"unavailable"), `ask_availability` creates one tentative hold per
offered slot (threading `classification.earliest_offer_time` into
`find_open_slots()` so a stated timeframe preference like "next week"
is respected instead of always offering starting today), `accept_slot`
confirms the matched hold, `irrelevant` is
a no-op (but still gets marked read, so spam isn't reclassified by
Gemini on every re-run). `classify_email()` returns only a proposed
*start* time for `propose_time`, so `agent.py` reuses
`gcalendar.slots.SLOT_DURATION` (30 min) as the assumed meeting length
for both the free/busy check and the booking. See
`specs/2026-07-09-agent-orchestration/spec.md`,
`specs/2026-07-09-polling-loop/spec.md`,
`specs/2026-07-12-draft-signature-name/spec.md`,
`specs/2026-07-12-earliest-offer-time/spec.md`, and
`specs/2026-07-12-verbatim-meeting-times/spec.md` for the full
decision log.

## auth/

OAuth2 flow (`google-auth-oauthlib`) and token storage/refresh for the
combined Gmail + Calendar scopes (`gmail.modify`, `gmail.compose`,
`gmail.settings.basic`, `calendar.events`, `calendar.freebusy`).
`google_auth.py` exposes `get_credentials()` — always import this
rather than touching `credentials.json`/`token.json` directly. Adding
a scope means any existing `token.json` was authorized under the old
set and must be regenerated (delete it, then the next run's
`_run_interactive_flow()` re-prompts for consent).

## gmail/

Gmail API wrapper. `client.py` builds the authenticated service via
`auth.get_credentials()`; `read.py` lists unread inbox messages,
fetches header metadata (`Message` dataclass) and body text, and marks
a message read via `mark_as_read()` (removes the `UNREAD` label, used
by `agent.py` once a message is successfully processed so re-running
`agent.py` doesn't reprocess it); `draft.py` creates threaded draft
replies (`In-Reply-To`/`References`/`threadId`); `profile.py`'s
`get_display_name()` reads the account's own configured "send mail
as" name (`users.settings.sendAs.list`, the `isPrimary` entry — needs
the `gmail.settings.basic` scope), used by `agent.py` to sign drafted
replies instead of a placeholder, falling back to the local part of
the email address if no display name is set. No sender/relevance
filtering here by design — that's `llm/`'s job.

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
dataclass); `find_open_slots()` takes an optional `earliest` that
pushes the starting point later than `now` (never earlier — clamped
via `max(current, earliest)`), fed from `llm.classify`'s
`earliest_offer_time` when the sender stated a timeframe preference;
`events.py` books
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
spec for the raise-vs-downgrade rule). `ask_availability` also carries
an optional `earliest_offer_time` (Gemini's relative-date reasoning
applied to timeframe phrases like "next week") that
`gcalendar.slots.find_open_slots()` uses to push where it starts
offering slots from — but a malformed value here falls back to `None`
instead of downgrading the whole classification, deliberately unlike
`proposed_time`/`accepted_slot_index`, since it's an optional
refinement and `ask_availability` stays fully actionable without it
(see `specs/2026-07-12-earliest-offer-time/spec.md`); `draft.py` has four
outcome-specific functions (not one polymorphic type) that draft reply
text via plain Gemini completions, one per calendar outcome, each
taking a `your_name: str` (the account's display name, fetched once
per run by `agent.py` via `gmail.profile.get_display_name()`) so the
prompt tells Gemini who to sign the reply as instead of leaving it a
placeholder. Gemini is never trusted to write an actual date/time into
the drafted text itself — it was found (live-verified against the
real API) to non-deterministically corrupt an exact time when asked
to freely reformat one into prose. Instead every function that has a
time to communicate asks Gemini to leave a literal token
(`[[MEETING_TIME]]` or, for the multi-slot case, `[[SLOT_LIST]]`)
where the value belongs; `_complete_with_placeholder()` then requires
that token to be present and substitutes it with the real,
deterministically-formatted value from `_format_range()` — raising
`ValueError` (routed through `agent.py`'s existing per-message
retry-next-run handling) if the placeholder is missing, rather than
risking an unverified or corrupted time reaching a draft. This
verify-then-substitute pattern is the general approach for any future
LLM output that must contain an exact, non-negotiable value — see
`specs/2026-07-12-verbatim-meeting-times/spec.md`. Pure module — no
Gmail/Calendar API calls happen here; the orchestrator (`agent.py`)
wires `llm/` together with `gmail/`/`gcalendar/`.

## config.py

Loads `.env` via `python-dotenv` and exposes `GEMINI_API_KEY` /
`GEMINI_MODEL` (shared by classification and drafting). Credential
paths for Google auth stay in `auth/google_auth.py`, not here.

## scripts/

One manual, real-network verification script per feature area
(`check_auth.py`, `check_gmail.py`, `check_gcalendar.py`,
`check_llm.py`) — run against real Gmail/Calendar/Gemini to sanity-check
a feature end to end, distinct from `tests/`'s mocked pytest suite. Run
as modules (`python -m scripts.check_auth`), not as scripts
(`python scripts/check_auth.py`), so their absolute imports
(`from auth...`, `from gmail...`) resolve against the repo root.

## tests/

pytest suite; mocks the Gmail/Calendar API clients (`unittest.mock`,
no real network calls). Config in `pyproject.toml`
(`[tool.pytest.ini_options]`).

## specs/

Per-feature spec/plan folders (`specs/<date>-<name>/spec.md` +
`plan.md`), scaffolded from `specs/_TEMPLATE/`. See git-workflow skill
for file-ownership rules.

---

Last structural update: 2026-07-12 (new `gmail/profile.py` reads the
account's real display name so drafted replies sign off with it
instead of a placeholder; `llm/draft.py`'s four functions and
`agent.py`'s threading updated accordingly; `agent.py` also now caps
each run's unread messages by both count and a 2-day window to avoid
re-hitting Gemini's free-tier rate limit; `llm.classify` now extracts
an optional `earliest_offer_time` for `ask_availability` so
`gcalendar.slots.find_open_slots()` respects a sender-stated timeframe
preference instead of always starting from `now`; `llm/draft.py` no
longer trusts Gemini to write dates/times into drafts itself —
verify-then-substitute a literal placeholder token instead, since
free-text reformatting was found to non-deterministically corrupt
exact times)
