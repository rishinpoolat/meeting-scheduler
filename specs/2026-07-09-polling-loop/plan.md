# Plan: mark-as-read + stale-hold sweep

**Status:** Approved
**Spec:** see ../spec.md
**Branch:** feature/polling-loop

## To Do

(nothing left)

## In Progress

(nothing left)

## Completed

- [x] Testing skill's quality gate: test-runner reported 97/97 passing
      (pytest/mypy/ruff all clean); code-reviewer verified `mark_as_read`
      against Gmail API conventions, confirmed the isolation try/except
      actually leaves a failed message unread (not just docstring
      trust), and confirmed `expire_stale_holds` is called
      signature-compatibly before the message loop. Reported 2 findings
      — developer chose to fix both:
      - Fixed: split the per-message try/except into two — one for
        fetch+`process_message`, one for `mark_as_read` — logged with
        distinct messages, so a `mark_as_read` failure (which can cause
        duplicate holds/drafts on retry, since `process_message` has no
        idempotency of its own) is diagnosable instead of looking
        identical to a safe pre-processing failure. New test
        `test_mark_as_read_failure_is_logged_distinctly_from_a_processing_failure`.
      - Fixed: added `test_sweep_failure_is_not_caught_and_propagates`,
        locking in the spec's decision that only per-message failures
        are caught, not the sweep.
      - 99/99 tests pass after the fixes, mypy/ruff clean.

- [x] `gmail/read.py`: added `mark_as_read(service, message_id) -> None`.
- [x] `agent.py`: `run_cycle` calls `expire_stale_holds` first, wraps
      each message's fetch+act+mark-read in one try/except with
      `logger.exception(...)` on failure. `main()` unchanged.
- [x] Unit tests:
      - `tests/test_gmail_read.py`: `mark_as_read` removes the UNREAD
        label.
      - `tests/test_agent.py` `TestRunCycle`: updated 3 existing tests
        for the new `expire_stale_holds`/`mark_as_read` calls; added
        cases for sweep-before-listing ordering, mark-read-only-on-
        success, process_message failure isolation (message left
        unread, next message still processed), get_message fetch
        failure isolation, mark_as_read failure isolation, and that
        the failure log includes the message ID.
      - 97/97 tests pass, `mypy .` and `ruff check .`/`ruff format .`
        all clean.
- [x] Integration test: not needed separately — `run_cycle`'s unit
      tests already exercise the full per-run flow end-to-end with
      collaborators mocked at the boundary.
- [x] Updated `CODEBASE_MAP.md` (`## agent.py`, `## gmail/`, "Last
      structural update"), `README.md` (Status section),
      `specs/ROADMAP.md` (Feature 6 ✅, wording adjusted for the
      descoped schedule, step 2's "poll cycle" language), `specs/INDEX.md`
      (new entry).
