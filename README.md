# meeting-scheduler

An agent that watches a Gmail inbox for meeting/scheduling enquiries
— e.g. sent via a portfolio site's contact form — and responds
autonomously: if the sender proposes a specific time and it's free, it
books the event on Google Calendar and drafts a confirmation reply; if
the sender asks for availability, it finds open slots on the calendar
— respecting any timeframe they mention (e.g. "next week") — and
drafts a reply listing 5 suitable times (spread across mornings and
afternoons, not clustered). Drafted replies sign off with the
account's real name and never contain a date/time written by the LLM
itself (see [Reliability notes](#reliability-notes)). All replies are
created as Gmail drafts for manual review/send — never auto-sent.

It runs entirely against **your own** Google account and Gemini API
key — nothing is shared or hosted. See [Setup](#setup) below to run it
against your own Gmail/Calendar with your own credentials.

## Stack

- Python
- Google Gemini API (`google-genai`, structured output) — for email
  classification and reply drafting
- Gmail API
- Google Calendar API
- OAuth2 (`google-auth-oauthlib`)

## Status

All features on the original roadmap are shipped: OAuth2 (Gmail +
Calendar), reading unread Gmail messages and drafting threaded
replies, the Google Calendar layer (free/busy checks, timeframe-aware
open-slot finding, confirmed booking, tentative holds), Gemini-based
email classification + reply drafting, and `agent.py` wiring all of
that into one run — sweeping stale holds, processing unread mail
(capped per run to stay under Gemini's free-tier limits), and marking
each handled message read so re-running doesn't redraft the same
replies. `agent.py` is a manually-run, single-pass script by design
(no scheduling loop — just run `python agent.py` whenever you want to
check for new mail).

Beyond the original roadmap, a round of testing against a real inbox
surfaced and fixed several reliability issues — see
[Reliability notes](#reliability-notes) below.

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
  risking a wrong time reaching a real recipient.
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

This project runs entirely against credentials you provide yourself —
your own Google Cloud OAuth client and your own Gemini API key. Nobody
else can see your inbox, calendar, or drafts; everything runs locally
on your machine.

### 1. Create a Google Cloud OAuth client

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
   and create (or select) a project.
2. **APIs & Services → Library** — enable the **Gmail API** and the
   **Google Calendar API**.
3. **APIs & Services → OAuth consent screen** — set User type to
   **External**, and add your own Gmail address as a **test user**
   (this keeps the app in testing mode, which is fine for personal
   use — no Google review needed).
4. **APIs & Services → Credentials → Create Credentials → OAuth
   client ID** — Application type **Desktop app**.
5. Download the resulting JSON, rename it to `credentials.json`, and
   place it at the repo root. This file is gitignored — it's your
   personal client secret and must never be committed.

### 2. Get a Gemini API key

Get a free key (no credit card required) from
[Google AI Studio](https://aistudio.google.com/apikey).

### 3. Configure environment variables

Copy `.env.example` to `.env` and fill in `GEMINI_API_KEY` with the
key from step 2:

```
cp .env.example .env
```

`.env` is gitignored — your key stays local. The free tier is
rate-limited both per minute *and* per day (as low as 20
requests/day on some models) — `agent.py` and `scripts/check_llm.py`
both pace/cap their own calls to stay under the per-minute limit, but
there's no getting around the daily cap if you're testing heavily;
expect a 429 if you exceed either. Optionally set `GEMINI_MODEL` in
`.env` to pin a specific model instead of the default
`gemini-flash-latest` alias — see
[Reliability notes](#reliability-notes) for why this project prefers
an alias over a pinned version.

### 4. Install dependencies

```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 5. Complete the OAuth consent flow

Run any `scripts/check_*.py` script once to open a browser, grant
consent, and cache a local, refreshable token:

```
python -m scripts.check_auth
```

This creates `token.json` at the repo root (also gitignored — it's
your personal access/refresh token). If you ever add a new scope to
`auth/google_auth.py`'s `SCOPES`, delete the cached `token.json` first
so the next run re-prompts for consent under the new scope set — an
old token silently keeps only the scopes it was originally granted.

### 6. Run it

```
python agent.py
```

Each run processes unread mail once and exits — there's no background
polling loop by design. Run it again (manually, or on your own cron/
scheduler) whenever you want to check for new mail. Check your Gmail
Drafts folder for what it produced; nothing is ever sent without you
reviewing and hitting send yourself.

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

- `agent.py` — entry point; one manually-run pass over unread mail.
- `auth/` — OAuth2 credential loading, caching, and refresh.
- `gmail/` — Gmail API wrapper (read unread mail, create draft replies).
- `gcalendar/` — Google Calendar API wrapper (free/busy, open slots,
  booking, tentative holds).
- `llm/` — Gemini-based email classification and reply drafting.
- `scripts/` — manual, real-network verification scripts (one per
  feature area).
- `tests/` — mocked pytest suite, no real network calls.

## Contributing

Issues and PRs are welcome. Internally this project develops every
feature through a spec/plan cycle before writing code, but that
history is kept as local, private development notes and isn't part of
the public repo — not required for outside contributions either, just
how the maintainer works.

## License

[MIT](LICENSE)
