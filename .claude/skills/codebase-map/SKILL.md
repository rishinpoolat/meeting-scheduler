---
name: codebase-map
description: How and when to update CODEBASE_MAP.md. Use this whenever a feature adds, removes, or renames a top-level folder, changes a module's responsibility, or establishes a new pattern future code should follow — not needed for changes that don't touch project structure.
---

CODEBASE_MAP.md (project root) is read every session before exploring
the file tree — it should answer "where does X live" faster than
searching. This skill governs keeping it accurate.

When to update it:

- A top-level folder is added, removed, or renamed
- A module's responsibility changes
- A new pattern is established that future code should follow

How to write entries:

- One folder per heading, 1-2 lines max
- Name the pattern to follow, not just what's there
- Update it in the same step as the code change — don't batch for later

This is a standing rule for the rest of the current task — if more
structural changes happen later in the same session, this still applies.
