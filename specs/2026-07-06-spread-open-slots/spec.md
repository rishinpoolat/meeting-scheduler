# Spec: Spread open slots across morning/afternoon

**Status:** Approved
**Created:** 2026-07-06

## What it does

Changes `find_open_slots` so the offered times spread out — at most
one slot in the morning and one in the afternoon per business day —
instead of clustering all 5 consecutive slots into the first available
morning.

## Decisions

1. Business hours stay 9am–5pm exactly (no evening extension).
2. Split point: an even 1pm split, no lunch gap — morning = 9:00–13:00, afternoon = 13:00–17:00 (4h/4h).
3. Spread strategy: at most one slot per half-day. Walk half-day windows in chronological order (day1 AM, day1 PM, day2 AM, day2 PM, ...), taking the earliest available 30-min slot in each half; skip a half entirely if it has no free 30-min gap (no compensating by doubling up the other half that day).
4. `LOOKAHEAD_BUSINESS_DAYS` stays 5 business days (up to 10 half-day windows) — a fully-free calendar only needs 3 business days (2+2+1) to fill 5 slots.
5. Still exactly ONE `freebusy().query()` call spanning the first window's start to the last window's end.
6. `freebusy.py` / `is_slot_free` unchanged.
7. `current == day_end` (17:00:00 exactly) now correctly excludes that day entirely (a minor, more-correct behavior delta vs. the previous literal edge case, not previously tested).

## Open questions

None — all resolved above.

## Out of scope

- No changes to `freebusy.py`, `events.py`, or the hold mechanism.
- No changes to business-hours bounds, meeting duration, or the 5-business-day lookahead constant beyond the new midday split.
- No holiday-calendar awareness (unchanged from Feature 3).

## Affected areas

- `gcalendar/slots.py` — `_business_hour_windows`/`_chunk_into_slots` replaced by `_half_day_windows`/`_first_slot_in_window`
- `tests/test_gcalendar_slots.py` — full scenario rewrite
- `CODEBASE_MAP.md` — `gcalendar/` entry's `slots.py` description updated to mention the half-day spread
