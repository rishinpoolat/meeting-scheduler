# Specs Index

> One-line log of **completed** features. Read this instead of opening
> every `specs/*/spec.md` — it costs far less context. Only open a
> specific feature's `spec.md`/`plan.md` when working directly on or
> near that area. See [`specs/ROADMAP.md`](./ROADMAP.md) for what's
> planned next. This file is shared/directly-editable (like
> `CODEBASE_MAP.md`), not owned by a single feature branch.

- **2026-07-06 — google-oauth**: OAuth2 for Gmail + Calendar.
  `auth/google_auth.py`'s `get_credentials()` caches/refreshes a token,
  falls back to interactive consent when missing/corrupt/unrefreshable.
  → [`specs/2026-07-06-google-oauth/`](./2026-07-06-google-oauth/)

- **2026-07-06 — gmail-read-draft**: List unread inbox messages (no
  relevance filtering — deferred to Claude classification) and create
  correctly threaded Gmail draft replies. `gmail/{client,read,draft}.py`.
  → [`specs/2026-07-06-gmail-read-draft/`](./2026-07-06-gmail-read-draft/)
