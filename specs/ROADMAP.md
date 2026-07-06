# Roadmap: meeting-scheduler

> Forward-looking plan. For what's already built, see
> [`specs/INDEX.md`](./INDEX.md) instead of reading every
> `specs/<date>-<name>/spec.md`. This file is shared/directly-editable
> (like `CODEBASE_MAP.md`), not owned by a single feature branch.

## The end-to-end flow (what we're building toward)

1. **Auth** — one-time OAuth2 consent, refreshable token stored
   locally, covering both Gmail and Calendar scopes.
2. **Poll** — list unread messages in the inbox (Gmail
   `users.messages.list`, `maxResults=50`). Only the 50 most recent
   unread are processed per cycle; anything beyond that waits for the
   next cycle. No sender/address filtering — deciding what's a real
   enquiry vs. spam/newsletters is Claude's job (step 3).
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
4. ⬜ **Next up** — **Claude classification** — `llm/`: given raw email text,
   classify intent and extract a proposed datetime, or flag "asking
   availability," and detect replies that accept one of a prior
   thread's offered slots. Anthropic API key via `ANTHROPIC_API_KEY`
   env var / `.env` (already gitignored), read by the `anthropic` SDK
   automatically — no OAuth-style consent flow needed for this one.
5. ⬜ **Wire the full cycle** — `agent.py` orchestrates 1–4 end to end
   for a single unread email, including matching a reply back to its
   original thread's holds.
6. ⬜ **Polling loop + idempotency** — repeat cycle on a schedule,
   dedupe/mark-processed handling, the 48-hour hold-expiry sweep,
   basic error logging.

## Known open decisions (surface these when spec'ing 3/4/5)

- Exact freebusy query shape and business-hours/timezone handling.
- How a reply email gets correlated to its Gmail thread ID for hold
  resolution.
- What happens if a sender accepts a slot *after* its hold already
  expired and got deleted (likely: re-check freebusy at that point and
  book if still free, else say so).
