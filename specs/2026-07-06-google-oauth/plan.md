# Plan: Google OAuth (Gmail + Calendar)

**Status:** Approved
**Spec:** see ../spec.md
**Branch:** feature/google-oauth

## To Do

(none remaining)

## In Progress

(none)

## Completed

- [x] `requirements.txt`: google-auth, google-auth-oauthlib,
      google-api-python-client, pytest, mypy, ruff
- [x] `auth/__init__.py`, `auth/google_auth.py` — SCOPES,
      CREDENTIALS_PATH/TOKEN_PATH constants, `get_credentials()`
- [x] `check_auth.py` — manual verification entrypoint
- [x] Unit tests (`tests/test_google_auth.py`), 5/5 passing:
  - valid cached token → returned as-is, no refresh, no flow
  - expired token + refresh_token present → refresh path taken, token
    file rewritten
  - refresh raises → falls back to interactive flow instead of
    propagating the error
  - token file missing → interactive flow invoked, result saved
  - token file present but corrupt/unparseable JSON → handled like
    "missing", not a crash
- [x] Integration test: intentionally skipped — needs the developer's
      live GCP credentials and a real browser consent click; not
      automatable/repeatable in a test suite. `check_auth.py` is the
      manual substitute (see spec's Prerequisite section) — still
      pending developer's manual GCP setup + one-time run.
- [x] test-runner: 5/5 pass (caught and fixed a real bug — plain
      `pytest` failed at collection due to missing pythonpath config,
      fixed via `pyproject.toml`).
- [x] code-reviewer: no blockers; fixed all flagged minors (redundant
      exception type, token.json now written 0600, two tests given
      stronger save-assertions, mypy python_version pinned).
- [x] `pyproject.toml` added: pytest pythonpath config, mypy
      python_version pin, mypy overrides for untyped Google libs.
