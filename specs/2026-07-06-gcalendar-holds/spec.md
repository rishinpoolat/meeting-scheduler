# Spec: Google Calendar read/write with tentative holds (`gcalendar/`)

**Status:** Approved
**Created:** 2026-07-06

## What it does

Adds a `gcalendar/` package that can: check whether a given time slot
is free, find up to 5 open 30-minute slots across the next 5 business
days, book a confirmed event, create a tentative "hold" event tagged
with a Gmail thread ID, confirm one hold while deleting its siblings,
and sweep-delete holds older than 48 hours. All Calendar writes
suppress Google's own attendee notification emails — this project's
only outbound channel is a manually-reviewed Gmail draft.

## Decisions

1. **Timezone**: read at runtime from `events().list(calendarId="primary", maxResults=1).execute()["timeZone"]` — deliberately *not* `calendars().get()` or `settings().get()`, both of which need scopes broader than the already-granted `calendar.events`/`calendar.freebusy`. This avoids a re-consent flow.
2. **Business hours**: 9am–5pm, Monday–Friday, no holiday awareness in v1.
3. **Default meeting duration**: 30 minutes — fixed for both slot-finding and booking, since Feature 4 (duration extraction) doesn't exist yet.
4. **Lookahead window**: next 5 business days for the open-slot finder.
5. **Attendees**: `book_event`/`create_hold` add the sender as a Calendar attendee, but every write (`insert`/`patch`/`delete`) passes `sendUpdates="none"` — Calendar must never auto-email anyone directly.
6. **Freebusy + tentative holds**: freebusy is governed by an event's `transparency` field (default `"opaque"`/busy), not its `status`. A `status: "tentative"` hold is still counted as busy in freebusy queries as long as `transparency` is never set. No extra field needed.
7. **Hold tagging**: `extendedProperties.private` with keys `scheduler_hold` (`"true"`/`"false"`, string) and `scheduler_thread_id` (the Gmail thread ID). `events().list(privateExtendedProperty=[...])` ANDs all given constraints — sufficient for "all holds" and "holds for one thread," but can't express OR-across-threads if that's ever needed later.
8. **Hold age check**: uses the event's native `created` timestamp (server-assigned, immutable, no extra write) rather than a custom stored timestamp. Calendar returns `created` as `...Z` UTC — needs `.replace("Z", "+00:00")` before `datetime.fromisoformat` on Python 3.10.
9. **Error handling**: mirrors `gmail/`'s "let `HttpError` propagate uncaught" convention everywhere, with one narrow deviation — `confirm_hold`'s sibling-delete loop and `expire_stale_holds`' delete loop each swallow a 404 (already-deleted, race-safe) and re-raise anything else, so one vanished event doesn't abort the rest of the batch.
10. **`confirm_hold` sequencing**: fetch siblings first, patch the target event (`status="confirmed"`, `scheduler_hold="false"` — this also makes it stop matching the sweep filter automatically), then delete the other siblings.
11. **`CALENDAR_ID = "primary"`** lives in `gcalendar/client.py` as the single shared constant other modules import, since there's no project-wide `config.py` yet.
12. **Module layout**: `client.py` (service + `CALENDAR_ID`), `freebusy.py` (timezone lookup + busy-interval query + `is_slot_free`), `slots.py` (`TimeSlot` dataclass + `find_open_slots`), `events.py` (`Hold` dataclass + `book_event`/`create_hold`/`list_holds`/`confirm_hold`/`expire_stale_holds`). Timezone lookup folds into `freebusy.py` rather than a separate file — it's only ever used there.
13. **Revised after code review**: `find_open_slots` raises `ValueError` if `now` is passed as a naive `datetime`, instead of silently letting `.astimezone()` interpret it in the machine's local timezone (which would produce wrong slot boundaries whenever the host's local tz differs from the calendar's). `check_gcalendar.py`'s `expire_stale_holds(max_age_hours=0)` call got a warning comment noting it sweeps *all* stale holds on the calendar, not just the ones the script created.

## Open questions

None — all resolved above.

## Out of scope

- Pagination on `events().list()` (single-user hold volume is well under one page).
- Non-30-minute meeting durations, holiday-calendar awareness.
- Matching an inbound reply to which of the 5 offered slots was accepted (Feature 5).
- Deciding what to do if a sender accepts a slot after its hold already expired and was swept (Feature 5) — `is_slot_free` is the primitive Feature 5 will reuse for that re-check.
- Any Claude/LLM involvement (Feature 4).
- `config.py` (still PLANNED; per-module constants stay the convention).

## Affected areas

- New: `gcalendar/__init__.py`, `client.py`, `freebusy.py`, `slots.py`, `events.py`
- New: `tests/test_gcalendar_freebusy.py`, `test_gcalendar_slots.py`, `test_gcalendar_events.py`
- New: `check_gcalendar.py` (manual E2E smoke script, repo root, mirrors `check_auth.py`/`check_gmail.py`)
- `CODEBASE_MAP.md` — `gcalendar/` entry flips from PLANNED to built
- `specs/ROADMAP.md` — Feature 3 checkbox ⬜ → ✅
- `specs/INDEX.md` — one new line on completion
