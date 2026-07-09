# Spec: mark-as-read + stale-hold sweep

**Status:** Approved
**Created:** 2026-07-09

## What it does

`agent.py` stays a manually-run, single-pass script — no internal
loop, no scheduling. This feature fixes correctness across repeated
manual runs: each run now marks every processed message as read (so
re-running `python agent.py` doesn't redraft replies for the same
messages) and sweeps holds older than 48 hours at the start of the
run. Per-message failures are isolated and logged rather than aborting
the whole run. This is Feature 6 in `specs/ROADMAP.md`, descoped from
its original "repeat cycle on a schedule" wording (see Decisions).

## Decisions

- **No scheduling, no internal loop.** An earlier design in this
  session explored both a `POLL_INTERVAL_SECONDS` sleep-loop and a
  daily-fixed-time (`2:30pm`) scheduler; the developer explicitly
  rejected both — `agent.py` should do exactly one pass per manual
  invocation, same as Feature 5 built it. `main()` is unchanged.
- **Mark ALL processed messages as read**, including
  `intent="irrelevant"` — otherwise spam/newsletters get reclassified
  by Gemini on every re-run forever. New `gmail.read.mark_as_read()`,
  already authorized by the existing `gmail.modify` OAuth scope.
- **Sweep once per run, before listing unread messages** —
  `gcalendar.events.expire_stale_holds()` (built in Feature 3, unused
  until now) runs at the top of `run_cycle`, so any holds it frees are
  visible to that same run's `list_holds` lookups.
- **Per-message error isolation covers the whole per-message body**
  (fetch, act, mark-read), not just `process_message` — a failure
  anywhere in that sequence is logged (with the message ID) and the
  message is left unread to retry on the next manual run; processing
  continues with the next message. This `try/except` is needed
  regardless (to decide whether to mark read), so basic error logging
  comes along for free.
- **Fetch/act failures and mark-as-read failures are two separate
  `try/except` blocks, logged with different messages.** Added after
  code review flagged a real consequence of the original single-block
  design: if `process_message` already succeeded (booked a meeting,
  created holds, or created a draft) and only the subsequent
  `mark_as_read` call fails, the message stays unread and gets fully
  reprocessed next run — since none of `process_message`'s handlers
  have their own idempotency check, that can create a duplicate hold
  or draft. The message still ends up unread either way (there's no
  way to force-mark it read without the failing API call succeeding),
  but the two failure modes now log distinctly — "leaving unread for
  retry" (safe: nothing happened yet) vs. "processed but failed to
  mark read; it may be reprocessed" (the message will be re-acted-on
  next run) — so this class of failure is diagnosable instead of
  silently identical to a safe one. Full idempotency at the
  `process_message` level (e.g. checking for an already-existing hold
  before creating another) was considered and ruled out as
  disproportionate scope for this feature.
- **`process_message`'s signature and its existing 12 tests are
  unchanged** — this feature only touches `run_cycle` and adds
  `gmail.read.mark_as_read`.
- **First use of the stdlib `logging` module in this codebase** — a
  module-level `logger = logging.getLogger(__name__)` in `agent.py`
  for `logger.exception(...)` calls. No `logging.basicConfig()` call
  is added since there's no long-running process to configure for;
  Python's default "handler of last resort" already prints
  `logger.exception` output to stderr.

## Open questions

(none — all resolved above)

## Out of scope

- Any form of scheduling, internal loop, or polling interval — this
  was explicitly descoped; `agent.py` remains a manually-invoked,
  single-pass script.
- No message-level retry cap — a message that always errors logs and
  retries every manual run indefinitely until fixed.
- No external scheduling support (cron, systemd, launchd, etc.) is
  documented or required — running `agent.py` is entirely up to the
  developer.

## Affected areas

- `agent.py` (`run_cycle` changed: sweep call, per-message
  try/except, mark-as-read)
- `gmail/read.py` (`mark_as_read` added)
- `tests/test_agent.py`, `tests/test_gmail_read.py`
- `CODEBASE_MAP.md`, `specs/ROADMAP.md`, `specs/INDEX.md`, `README.md`
