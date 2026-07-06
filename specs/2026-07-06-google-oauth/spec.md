# Spec: Google OAuth (Gmail + Calendar)

**Status:** Approved
**Created:** 2026-07-06

## What it does

One-time interactive OAuth2 consent for combined Gmail + Calendar
access; caches a refreshable token locally so every later feature can
get an authenticated client without re-prompting.

## Decisions

- Flow: Installed-App (Desktop) flow via
  `google_auth_oauthlib.flow.InstalledAppFlow.run_local_server(port=0)`
  — opens the user's browser once for consent, receives the callback
  on a locally-bound port.
- One OAuth client, one consent screen, requesting all scopes the
  whole roadmap needs up front (avoids a second re-consent flow later
  when Calendar/draft features land):
  - `gmail.modify` — read messages + manage labels (for the later
    mark-as-processed step)
  - `gmail.compose` — create drafts (for the later reply-drafting step)
  - `calendar.events` — create/update/delete events (bookings + holds)
  - `calendar.freebusy` — freebusy queries (availability checks)
- File layout: `credentials.json` (OAuth client secret, developer-
  provided, gitignored) and `token.json` (cached access/refresh token,
  written by our code, gitignored), both at repo root.
- Module: `auth/google_auth.py` exposing `get_credentials()`:
  - `token.json` exists and credentials valid → return as-is.
  - exists, expired, has `refresh_token` → refresh via `Request()`,
    rewrite `token.json`.
  - refresh fails (e.g. revoked/invalid_grant) → discard the stale
    token and fall back to a fresh interactive consent, rather than
    crashing.
  - missing or unreadable/corrupt `token.json` → run the interactive
    flow via
    `InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)`,
    save the result.
- A tiny root-level script, `check_auth.py`, calls `get_credentials()`
  and then `gmail.users().getProfile(userId="me").execute()`, printing
  the authenticated email address — the manual end-to-end check.

## Open questions

(none — resolved above)

## Out of scope

- Reading/listing actual unread messages
- Any Calendar read/write
- Any drafting
- Any Claude call

All of the above are later features in the roadmap.

## Affected areas

- `auth/` (new package)
- `requirements.txt` (new — first real dependency file)
- `check_auth.py` (new)
- `tests/test_google_auth.py` (new)

## Prerequisite (developer, one-time, outside this repo)

Needs a Google Cloud OAuth client before end-to-end verification is
possible:

1. https://console.cloud.google.com/ → create/select a project.
2. APIs & Services → Library → enable **Gmail API** and **Google
   Calendar API**.
3. APIs & Services → OAuth consent screen → User type **External** →
   add your own Gmail address as a **test user**.
4. APIs & Services → Credentials → Create Credentials → OAuth client
   ID → Application type **Desktop app**.
5. Download the JSON, rename to `credentials.json`, place at repo
   root (already gitignored).
