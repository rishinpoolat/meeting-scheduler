# meeting-scheduler

An agent that watches a Gmail inbox for meeting/scheduling enquiries
sent via a portfolio website's contact email and responds
autonomously: if the sender proposes a specific time and it's free, it
books the event on Google Calendar and drafts a confirmation reply; if
the sender asks for availability, it finds open slots on the calendar
and drafts a reply listing 5 suitable times. All replies are created
as Gmail drafts for manual review/send — never auto-sent.

**Stack:** Python, Google Gemini API (google-genai, structured output),
Gmail API, Google Calendar API, OAuth2 (google-auth-oauthlib).

## Commands

- `pip install -r requirements.txt` — install deps
- `python agent.py` — run one polling cycle
- `pytest` — run tests
- `mypy .` — typecheck
- `ruff check .` — lint
- `ruff format .` — format

> `requirements.txt` doesn't exist yet — it gets created (with pinned
> deps) when the first feature scaffolds real code.

## Architecture

See @CODEBASE_MAP.md for folder-by-folder layout. Read it before
grepping — it should answer "where does X live" faster than searching.

See @specs/ROADMAP.md for the planned feature sequence and the
end-to-end design (including decisions not yet implemented, like the
Feature 3 tentative-hold mechanism).

See @specs/INDEX.md for a one-line log of *completed* features. Read
this, not every `specs/<date>-<name>/spec.md` — only open a specific
feature's spec.md/plan.md when working directly on or near that area.

## Workflow

Every feature goes through plan mode with explicit developer approval
before any code is written.

**Always-loaded rules** (apply to nearly every task, see .claude/rules/):

- .claude/rules/plan-mode.md — the approval gate, mandatory

**On-demand skills** (loaded only when relevant, see .claude/skills/):

- feature-checklist — what to consider before/while planning a feature
- testing — mandatory test + review workflow after implementation
- git-workflow — branching conventions, where plans live
- codebase-map — when/how to update CODEBASE_MAP.md

Skills are auto-discovered by Claude when a task matches their
description, so they don't cost context until actually needed — unlike
the rule above, which is read on most tasks regardless.

## Code style

- Type hints required on all function signatures — enforced by `mypy`.
- Formatting and lint rules are owned by `ruff` (`ruff format` /
  `ruff check`) — don't hand-debate style, run the tool.
- PEP 8 naming: `snake_case` for functions/variables, `PascalCase` for
  classes.
