# meeting-scheduler

An agent that watches a Gmail inbox for meeting/scheduling enquiries
sent via a portfolio website's contact email and responds
autonomously: if the sender proposes a specific time and it's free, it
books the event on Google Calendar and drafts a confirmation reply; if
the sender asks for availability, it finds open slots on the calendar
and drafts a reply listing 5 suitable times (spread across mornings
and afternoons, not clustered). All replies are created as Gmail
drafts for manual review/send — never auto-sent.

## Stack

- Python
- Google Gemini API (`google-genai`, structured output) — for email
  classification and reply drafting
- Gmail API
- Google Calendar API
- OAuth2 (`google-auth-oauthlib`)

## Status

Currently implemented: OAuth2 (Gmail + Calendar), reading unread Gmail
messages and drafting threaded replies, the Google Calendar layer
(free/busy checks, open-slot finding, confirmed booking, tentative
holds), and Gemini-based email classification + reply drafting. The
end-to-end polling loop (`agent.py`) is not built yet. See
[`specs/ROADMAP.md`](specs/ROADMAP.md) for the full planned sequence
and [`specs/INDEX.md`](specs/INDEX.md) for a log of what's shipped.

## Setup

1. Create a Google Cloud project with the Gmail and Calendar APIs
   enabled, and download an OAuth2 `credentials.json` into the repo
   root (see [`specs/2026-07-06-google-oauth/`](specs/2026-07-06-google-oauth/)
   for the full one-time setup steps).
2. Install dependencies:

   ```
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Run any `check_*.py` script once to complete the interactive OAuth
   consent flow and cache a local token (e.g. `python check_auth.py`).

## Commands

| Command | Purpose |
| --- | --- |
| `pip install -r requirements.txt` | Install dependencies |
| `python agent.py` | Run one polling cycle (not built yet) |
| `python check_auth.py` | Manually verify OAuth is working |
| `python check_gmail.py` | Manually verify Gmail read/draft |
| `python check_gcalendar.py` | Manually verify Calendar free/busy, slots, and holds |
| `python check_llm.py` | Manually verify Gemini classification and reply drafting |
| `pytest` | Run tests |
| `mypy .` | Typecheck |
| `ruff check .` | Lint |
| `ruff format .` | Format |

## Project layout

See [`CODEBASE_MAP.md`](CODEBASE_MAP.md) for a folder-by-folder
breakdown of what lives where and why.
