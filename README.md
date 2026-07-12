# meeting-scheduler

An agent that watches a Gmail inbox for meeting/scheduling enquiries
sent via a portfolio website's contact email and responds
autonomously: if the sender proposes a specific time and it's free, it
books the event on Google Calendar and drafts a confirmation reply; if
the sender asks for availability, it finds open slots on the calendar
— respecting any timeframe they mention (e.g. "next week") — and
drafts a reply listing 5 suitable times (spread across mornings and
afternoons, not clustered). Drafted replies sign off with the
account's real name and never contain a date/time written by the LLM
itself (see [Reliability notes](#reliability-notes)). All replies are
created as Gmail drafts for manual review/send — never auto-sent.

## Stack

- Python
- Google Gemini API (`google-genai`, structured output) — for email
  classification and reply drafting
- Gmail API
- Google Calendar API
- OAuth2 (`google-auth-oauthlib`)

## Status

All features on the original [roadmap](specs/ROADMAP.md) are shipped:
OAuth2 (Gmail + Calendar), reading unread Gmail messages and drafting
threaded replies, the Google Calendar layer (free/busy checks,
timeframe-aware open-slot finding, confirmed booking, tentative
holds), Gemini-based email classification + reply drafting, and
`agent.py` wiring all of that into one run — sweeping stale holds,
processing unread mail (capped per run to stay under Gemini's
free-tier limits), and marking each handled message read so
re-running doesn't redraft the same replies. `agent.py` is a
manually-run, single-pass script by design (no scheduling loop — just
run `python agent.py` whenever you want to check for new mail).

Beyond the original roadmap, a round of testing against a real inbox
surfaced and fixed several reliability issues — see
[Reliability notes](#reliability-notes) below and
[`specs/INDEX.md`](specs/INDEX.md) for the full log of what's shipped
(each entry links to a `spec.md`/`plan.md` with the full decision
log, including root-cause analysis for the reliability fixes).

## Reliability notes

A handful of bugs only showed up once this agent was pointed at a
real inbox rather than mocked tests, and are worth knowing about:

- **LLMs can't be trusted to reproduce exact values verbatim.**
  Gemini was found, via live testing, to non-deterministically corrupt
  meeting times when asked to reword a correct value into friendly
  prose (a real drafted confirmation showed the wrong time). Fixed
  structurally: Gemini now leaves a placeholder token instead of
  writing dates/times itself, and Python substitutes the
  guaranteed-correct value — raising an error (safely retried next
  run) if the placeholder is ever missing or duplicated, rather than
  risking a wrong time reaching a real recipient. See
  [`specs/2026-07-12-verbatim-meeting-times/`](specs/2026-07-12-verbatim-meeting-times/).
- **Gemini's free tier has both a per-minute *and* a daily quota**
  (as low as 20 requests/day on some models) — a real run hit both.
  `agent.py` caps unread polling by count and a 2-day window, and
  disables Gemini's "thinking" tokens (`thinking_budget=0`) for the
  small classification/drafting tasks here, since those tokens share
  the same output budget and were silently truncating responses.
- **Model names get deprecated without much warning.** `gemini-2.5-flash`
  was sunset for new accounts mid-session; `config.py` now defaults to
  `gemini-flash-latest` (an alias, not a pinned version) to avoid
  needing another manual fix the next time this happens.
- **The Calendar API's default ordering isn't guaranteed** — when a
  sender accepts one of several offered slots, matching "the second
  option" back to the right Calendar hold relies on
  `list_holds()`'s returned order matching the order slots were
  originally offered in. This has matched correctly in practice, but
  isn't enforced by an explicit `orderBy` — worth being aware of if a
  wrong-slot-confirmed bug ever surfaces.

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

3. Run any `scripts/check_*.py` script once to complete the interactive
   OAuth consent flow and cache a local token (e.g.
   `python -m scripts.check_auth`). If you ever add a new scope to
   `auth/google_auth.py`'s `SCOPES` (e.g. `gmail.settings.basic`, added
   for `gmail/profile.py`), delete the cached `token.json` first so the
   next run re-prompts for consent under the new scope set — an old
   token silently keeps only the scopes it was originally granted.
4. Get a free Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)
   (no credit card required) and copy `.env.example` to `.env`,
   filling in `GEMINI_API_KEY`. The free tier is rate-limited both
   per minute *and* per day (as low as 20 requests/day on some
   models) — `agent.py` and `scripts/check_llm.py` both pace/cap
   their own calls to stay under the per-minute limit, but there's no
   getting around the daily cap if you're testing heavily; expect a
   429 if you exceed either. Optionally set `GEMINI_MODEL` in `.env`
   to pin a specific model instead of the default `gemini-flash-latest`
   alias — see [Reliability notes](#reliability-notes) for why this
   project prefers an alias over a pinned version.

## Commands

| Command | Purpose |
| --- | --- |
| `pip install -r requirements.txt` | Install dependencies |
| `python agent.py` | Run one polling cycle |
| `python -m scripts.check_auth` | Manually verify OAuth is working |
| `python -m scripts.check_gmail` | Manually verify Gmail read/draft |
| `python -m scripts.check_gcalendar` | Manually verify Calendar free/busy, slots, and holds |
| `python -m scripts.check_llm` | Manually verify Gemini classification and reply drafting |
| `pytest` | Run tests |
| `mypy .` | Typecheck |
| `ruff check .` | Lint |
| `ruff format .` | Format |

Scripts under `scripts/` are run as modules (`python -m scripts.x`, not
`python scripts/x.py`) so their `from auth...`/`from gmail...` etc.
imports resolve against the repo root.

## Project layout

See [`CODEBASE_MAP.md`](CODEBASE_MAP.md) for a folder-by-folder
breakdown of what lives where and why.
