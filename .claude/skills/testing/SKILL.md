---
name: testing
description: Mandatory test and review workflow to run after implementing a feature, before marking anything Completed in plan.md and before committing. Use this whenever a feature's sub-tasks are all done and it's time to verify the work before closing it out.
---

After implementing a feature (all sub-tasks in plan.md done), before
marking anything Completed:

1. Dispatch the test-runner subagent to run the full test suite.
2. Dispatch the code-reviewer subagent to check the diff — including
   the quality of any tests written for this feature, not just the
   implementation.
3. Run both in parallel, not sequentially.
4. Do not mark the feature Completed in plan.md until:
   - test-runner reports a pass, AND
   - code-reviewer has reported back (developer decides whether to act
     on findings — code-reviewer flags, it doesn't block)
5. If tests fail: report back to the developer with specifics. Do not
   attempt silent fixes without flagging what broke and why.

## Pre-commit approval gate (separate from the above)

A passing test run is NOT by itself authorization to commit. Tests only
verify that the code does what the tests check for — they don't verify
the tests check for the right things, and they can't catch a feature
that works but wasn't actually what was wanted.

Before committing (per git-workflow skill):

1. Summarize for the developer: test-runner's result, and code-reviewer's
   findings (even if "none").
2. Explicitly ask for commit approval — e.g. "tests pass, code-reviewer
   found no issues, ready to commit — go ahead?"
3. Wait for an explicit yes. Do not commit on an assumed approval or
   because time has passed without objection.
4. If the developer raises a concern instead of approving, address it
   before re-asking — do not commit anyway.

This is a standing rule for the rest of this task — if more sub-tasks
get added to the feature later in the same session, both the quality
gate and the pre-commit approval apply again before that work is
committed.
