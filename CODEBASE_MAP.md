# Codebase Map

> A table of contents for the project. Read this before exploring the
> file tree or grepping — update it whenever folder structure or key
> files change. Shared across the team — keep entries scoped to your
> own feature's area to minimize overlap with concurrent edits from
> others.

> **Nothing below except `specs/` is built yet.** Entries marked
> PLANNED describe the intended structure so features can be planned
> against it; drop the marker once each is actually built.

## agent.py (PLANNED)

Entry point. Orchestrates one polling cycle: fetch unread emails,
classify intent, act (book event or find slots), draft reply.

## auth/ (PLANNED)

OAuth2 flow (`google-auth-oauthlib`) and token storage/refresh for the
combined Gmail + Calendar scopes.

## gmail/ (PLANNED)

Gmail API wrapper: list/read unread messages, create draft replies.

## gcalendar/ (PLANNED)

Google Calendar API wrapper: free/busy check, open-slot finding, event
creation. Named `gcalendar/`, not `calendar/`, to avoid shadowing
Python's stdlib `calendar` module.

## llm/ (PLANNED)

Claude tool-use orchestration: classifies each email (proposes a
specific time vs. asks for availability), decides the action, drafts
the reply text.

## config.py (PLANNED)

Credential paths, polling settings, constants.

## tests/ (PLANNED)

pytest suite; mocks the Gmail/Calendar API clients.

## specs/

Per-feature spec/plan folders (`specs/<date>-<name>/spec.md` +
`plan.md`), scaffolded from `specs/_TEMPLATE/`. See git-workflow skill
for file-ownership rules.

---

Last structural update: 2026-07-06
