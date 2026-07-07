# Spec: Claude Email Classification + Reply Drafting

**Status:** Approved
**Created:** 2026-07-07

## What it does

Given an inbound Gmail message, classifies the sender's scheduling
intent and extracts the data needed to act on it (a proposed datetime,
or which previously-offered hold they're accepting), using Claude tool
use for structured output. Separately, given a calendar-action outcome,
drafts the natural-language reply body text via Claude. Both are pure
functions — no Gmail/Calendar API calls happen inside `llm/`.

## Decisions

1. **Body access**: new `gmail.read.get_message_body(service, message_id) -> str`
   fetches `format="full"`, recursively walks `payload.parts`, returns
   the first `text/plain` leaf (base64url-decoded, manually padded).
   HTML-only emails yield `""` — no HTML-to-text conversion (explicit
   out-of-scope).
2. **`config.py` (new, root)** loads `.env` via `python-dotenv` and
   exposes `ANTHROPIC_API_KEY: str | None` and `CLAUDE_MODEL: str`
   (default `"claude-sonnet-5"`, overridable via env var). The key is
   validated **lazily** inside `llm.client.get_client()`, not at
   `config.py` import time — an eager check would crash every
   `import llm.classify` (including in the test suite) in any
   environment without a real key configured, mirroring how
   `auth.get_credentials()` — not `gmail/client.py` — is the sole OAuth
   validation gate.
3. **`llm/client.py`**: `get_client() -> Any` returns
   `anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)`, raising
   `RuntimeError` if the key is missing. Mirrors `gmail/client.py` /
   `gcalendar/client.py`'s `get_service()` one-liner shape.
4. **`llm/classify.py`**:
   - `Classification` dataclass: `intent: Literal["propose_time",
     "ask_availability", "accept_slot", "irrelevant"]`,
     `proposed_time: datetime | None`, `matched_hold: Hold | None`.
   - `classify_email(client: Any, message: Message, body: str, now: datetime, candidate_holds: list[Hold]) -> Classification`.
     `now` has **no default** (unlike `find_open_slots`) since `llm/`
     owns no calendar timezone — a silent local-machine-time fallback
     would repeat the exact naive-`now` bug `find_open_slots` was
     patched for (gcalendar spec Decision 13). Raises `ValueError` if
     `now` is naive.
   - Uses Anthropic tool use with a forced `tool_choice` (a single
     `record_classification` tool) so the response always contains
     `intent`, a nullable `proposed_time` (ISO 8601 string, computed by
     Claude relative to the `now` given in the prompt), and a nullable
     `accepted_slot_index` (1-based index into a numbered list of
     `candidate_holds` shown in the prompt — Claude returns an index,
     never a real Calendar event ID; Python maps it back to the actual
     `Hold`).
   - **Response-boundary rule**: no `tool_use` block in the response at
     all → hard contract violation → raise `ValueError` (same treatment
     as an unexpected `HttpError` elsewhere in this codebase). An
     out-of-range `accepted_slot_index`, or an unparseable/naive
     `proposed_time` when `intent == "propose_time"` → ordinary,
     expected model fuzziness → **downgrade** to
     `Classification(intent="irrelevant", proposed_time=None, matched_hold=None)`,
     never raise. Downgrading is the only choice that can never cause
     an incorrect auto-book or false accept-confirmation.
   - `Classification.matched_hold` stores the full `Hold` (not just its
     id) since it's already validated against `candidate_holds` and
     Feature 5 needs both `hold.id` (for `confirm_hold`) and
     `hold.start`/`end` (for drafting).
5. **`llm/draft.py`**: four concrete functions, one per outcome (not one
   polymorphic outcome type, per the locked-in scope decision):
   - `draft_booking_confirmation(client, message, start, end) -> str`
   - `draft_time_unavailable(client, message, requested_start, requested_end) -> str`
   - `draft_slot_offer(client, message, slots: list[TimeSlot]) -> str`
   - `draft_slot_confirmed(client, message, hold: Hold) -> str`

   Each prompts Claude with a greeting name parsed from
   `message.from_address` (shared private helper `_greeting_name`),
   `message.subject`, and only the outcome-specific data — **not** the
   original email body, since intent is already resolved by
   `classify_email` and drafting shouldn't re-interpret the original
   ask. A shared private helper `_complete(client, prompt) -> str`
   wraps the `client.messages.create(...)` call and extracts
   `response.content[0].text.strip()`, raising `ValueError` if
   `response.content` is empty (same hard-contract-violation treatment
   as classify's missing tool_use block).
6. **Model config**: one shared `config.CLAUDE_MODEL` constant used by
   both classification and drafting.
7. **No dedicated test files for `config.py` or `llm/client.py`** —
   matches the existing project precedent that trivial
   `get_service()`/`get_client()` one-liners aren't unit tested
   (`gmail/client.py`, `gcalendar/client.py` have none today).
8. **`check_llm.py`** added as a manual smoke-test script (mirrors
   `check_gcalendar.py`/`check_gmail.py`), exercising all four intents
   and all four draft functions against fixture data, printed for human
   review. No live Gmail/Calendar calls needed since `llm/` is pure.
9. **Post-review fixes** (found by `code-reviewer`, both fixed):
   - `_parse_proposed_time` normalizes a `Z` UTC suffix to `+00:00`
     before calling `datetime.fromisoformat` — this project targets
     Python 3.10 (native `Z` support only landed in 3.11), so a
     `Z`-suffixed `proposed_time` would otherwise silently downgrade a
     valid `propose_time` classification to `irrelevant`.
   - `_find_plain_text` now skips `text/plain` parts marked
     `Content-Disposition: attachment`, so a `.txt` attachment ahead of
     the real body in MIME part order isn't mistaken for it.
   - **Deliberately not fixed** (documented limitation, not a bug):
     `get_message_body` only reads inline `body.data`. Gmail omits
     inline data for large parts (`attachmentId`-only), which this
     function can't distinguish from an HTML-only email — both return
     `""`. Fetching `attachments.get()` for large plain-text bodies is
     out of scope for this pass (see Out of scope).
   - **Deliberately not fixed** (minor, low-value): `_match_hold`'s
     `isinstance(index, int)` check also accepts `bool` (Python
     subclassing quirk) — unreachable in practice since the JSON schema
     types `accepted_slot_index` as `["integer", "null"]`.
     `_greeting_name` doesn't decode RFC 2047 MIME-encoded display
     names (garbled greeting for some non-ASCII sender names) — deferred
     to a later pass if it comes up in practice.

## Open questions

None — all resolved above.

## Out of scope

- Any Gmail/Calendar API calls from within `llm/` (Feature 5's job).
- End-to-end orchestration / deciding which action to take from a
  `Classification` (Feature 5, `agent.py`).
- 48h hold-expiry sweep, polling loop (Feature 6).
- Meeting-duration extraction — stays fixed at 30 minutes, unchanged.
- HTML-to-text conversion for HTML-only emails.
- Fetching large plain-text bodies via Gmail's `attachments.get()` —
  `get_message_body` only reads inline `body.data`; a body large enough
  that Gmail omits inline data returns `""`, same as an HTML-only email.
- RFC 2047 MIME-decoding of non-ASCII sender display names in
  `_greeting_name`.

## Affected areas

New:
- `llm/__init__.py`, `llm/client.py`, `llm/classify.py`, `llm/draft.py`
- `config.py`
- `tests/test_llm_classify.py`, `tests/test_llm_draft.py`
- `check_llm.py`
- `.env.example`

Modified:
- `gmail/read.py` (+`get_message_body`)
- `tests/test_gmail_read.py` (new cases)
- `requirements.txt` (+`anthropic`, `+python-dotenv`)

Trailing:
- `CODEBASE_MAP.md` — flip `llm/` and `config.py` from PLANNED to built.
- `specs/ROADMAP.md` — Feature 4 checkbox ⬜ → ✅.
- `specs/INDEX.md` — one new line for this feature.
