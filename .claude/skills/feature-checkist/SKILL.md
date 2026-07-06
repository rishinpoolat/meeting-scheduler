---
name: feature-checklist
description: What to consider before/while planning a feature — checking for existing functionality, deciding if a spec is warranted, scoping, test coverage needs, and overlap with other in-flight work. Also covers how to ask concrete clarifying questions. Use this whenever a feature is requested and plan mode is being entered.
---

# Before Building a Feature

Considerations Claude must run through before/while proposing a plan:

- Check CODEBASE_MAP.md first — does similar functionality already
  exist? Don't duplicate.
- Does this need a spec? (multi-file, ambiguous, security/data-sensitive
  → yes. Small/obvious → plan mode only, no spec doc needed.)
- What's explicitly out of scope for this pass?
- Which existing tests might this affect, and will this feature need new
  unit tests, an integration test, or both? (see plan.md template)
- Does this change cross into another developer's in-flight feature
  (check open branches/specs/ folders)? Flag it if so — don't silently
  touch shared code without calling it out.

## Asking concrete clarifying questions, not generic ones

"Surface open questions instead of guessing" means asking the _specific_
question the feature actually needs answered — not a vague "any
preferences?" Match the question to the domain:

Example — request: "I want authentication set up in the project"
Good clarifying questions:

- Email/password, Google OAuth, or both?
- Does this need email verification, or is signup immediate?
- Password reset flow needed now, or later?
- Any role/permission distinction (admin vs. regular user), or all
  users equal for now?

Bad: a single generic "what are your requirements for authentication?"
— this pushes the thinking back onto the developer instead of narrowing
down the real decision points the way a colleague familiar with the
domain would.

Ask the smallest set of concrete questions that actually changes the
plan depending on the answer — not every conceivable question, just the
ones where different answers lead to a different implementation.

This is a standing rule for the rest of the current task — if more
features get requested later in the same session, this checklist
applies again each time.
