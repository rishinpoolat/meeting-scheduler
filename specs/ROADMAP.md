# Roadmap: meeting-scheduler

> Forward-looking plan. For what's already built, see
> [`specs/INDEX.md`](./INDEX.md) instead of reading every
> `specs/<date>-<name>/spec.md`. This file is shared/directly-editable
> (like `CODEBASE_MAP.md`), not owned by a single feature branch.

## The end-to-end flow (what we're building toward)

1. **Auth** — one-time OAuth2 consent, refreshable token stored
   locally, covering both Gmail and Calendar scopes.
2. **Poll** — list unread messages in the inbox (Gmail
   `users.messages.list`, `maxResults=50`) each time `agent.py` is run
   (a manually-invoked, single-pass script — no internal scheduling).
   Only the 50 most recent unread are processed per run; anything
   beyond that waits for the next run. No sender/address filtering —
   deciding what's a real enquiry vs. spam/newsletters is the LLM's
   job (step 3).
3. **Classify** — hand the email text to Claude (tool use) to decide:
   proposes a specific time / asks for availability / neither (skip).
4. **Check calendar** — Calendar `freebusy.query` (or `events.list`)
   against the extracted time, or across the next N business days when
   finding open slots. Freebusy naturally includes both real meetings
   *and* this agent's own tentative holds (see step 5), so a slot
   already offered to someone else is automatically excluded.
5. **Act**:
   - Specific time + free → `events.insert` (confirmed) to book it,
     then draft a confirmation reply.
   - Specific time + busy (real meeting or someone else's pending
     hold) → draft a reply saying so (no auto rescheduling in v1).
   - Asking for availability → compute 5 open slots, create a
     **tentative hold event per slot** tagged with this email thread's
     ID (via Calendar `extendedProperties.private`), then draft a
     reply listing all 5.
6. **Draft, never send** — every reply is a Gmail `drafts.create`, for
   manual review.
7. **Resolve holds on reply** — when a follow-up reply on that thread
   arrives accepting one of the 5: confirm that one hold (status →
   confirmed) and delete the other 4 holds for that thread. If the
   reply proposes a different time entirely, treat it like any other
   specific-time request and separately let this thread's unclaimed
   holds expire.
8. **Expire stale holds** — each poll cycle also sweeps for hold events
   older than 48 hours with no confirmation and deletes them, freeing
   those slots back into the pool.
9. **Don't reprocess** — mark the source email read (or apply a
   processed label) once handled.

## Feature sequence

Each feature gets its own plan-mode cycle, `feature/<name>` branch, and
`specs/<date>-<name>/` folder — this roadmap is only the ordering, not
a substitute for those. Status is kept up to date here as features
ship (see `specs/INDEX.md` for the completed ones' details).

1. ✅ **Done** — Google OAuth (Gmail + Calendar). See
   `specs/INDEX.md`.
2. ✅ **Done** — Read unread Gmail messages + create a draft reply
   (no relevance filtering — that's step 4 below). See
   `specs/INDEX.md`.
3. ✅ **Done** — Google Calendar read + write, with tentative holds.
   See `specs/INDEX.md`.
4. ✅ **Done** — **LLM classification + reply drafting** — `llm/`: given raw
   email text, classifies intent and extracts a proposed datetime, or
   flags "asking availability," and detects replies that accept one of
   a prior thread's offered slots. Also drafts the reply text for each
   calendar outcome. Originally built on Anthropic (Claude), migrated
   to Google Gemini (free tier) shortly after. See `specs/INDEX.md`.
5. ✅ **Done** — **Wire the full cycle** — `agent.py` orchestrates 1–4
   end to end for a single unread email, including matching a reply
   back to its original thread's holds. See `specs/INDEX.md`.
6. ✅ **Done** — **Idempotency + basic error logging** — descoped from
   its original "repeat cycle on a schedule" wording: the developer
   decided `agent.py` should stay a manually-run, single-pass script
   (no internal loop, no polling interval). What shipped: mark-
   processed handling (so re-running doesn't redraft the same
   replies), the 48-hour hold-expiry sweep wired into each run, and
   per-message error isolation/logging. See `specs/INDEX.md`.

## Known open decisions

All resolved as of Feature 5 (`specs/2026-07-09-agent-orchestration/`):

- Exact freebusy query shape and business-hours/timezone handling —
  resolved in Feature 3 (`gcalendar-holds`).
- How a reply email gets correlated to its Gmail thread ID for hold
  resolution — resolved in Feature 5: `agent.py` unconditionally calls
  `gcalendar.events.list_holds(thread_id=message.thread_id)` before
  classifying every message, regardless of whether it's a fresh thread
  or a reply.
- What happens if a sender accepts a slot *after* its hold already
  expired and got deleted — resolved in Feature 5, differently than
  originally guessed here: since a swept hold leaves no record behind,
  `classify_email` can't distinguish this case from a genuinely
  irrelevant reply, so it's treated the same way (skip, no draft) —
  the "re-check freebusy and book if still free" idea would need
  `llm/classify.py` schema changes and was ruled out of scope.
