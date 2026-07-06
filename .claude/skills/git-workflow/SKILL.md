---
name: git-workflow
description: Branching, commit, and file-ownership conventions for this project's per-feature spec/plan structure. Use when a plan has just been approved (branch creation), when committing, opening a PR, or when unsure whether you're allowed to edit a given specs/ file.
---

## Branch creation (right after plan approval)

Once the developer approves a plan (per plan-mode.md) and plan.md has
been created:

1. Create a new feature branch before writing any implementation code.
   Branch name: (fill in this project's convention, e.g.
   feature/<short-name>)
2. All implementation, spec.md, and plan.md for this feature live on
   this branch until merge.
3. Do not implement directly on main/develop.

## File ownership

- One feature = one branch = one specs/<date>-<name>/ folder
- plan.md and spec.md live with the feature, not in a shared root file
- Never edit another feature's plan.md or spec.md — read-only if you
  need to reference it
- CODEBASE_MAP.md is the exception — it's shared and directly editable,
  since most features touch different, non-overlapping sections of it

## Commit (after the testing skill's pre-commit approval step)

- Do not commit until the testing skill's quality gate has completed AND
  the developer has given explicit pre-commit approval (see
  .claude/skills/testing/SKILL.md) — a passing test run alone is not
  authorization to commit.
- Commit messages: (fill in this project's convention)
- One commit per logical step is preferred over one giant commit at the
  end, but never commit code that hasn't passed the quality gate.

This applies for the rest of the current task — if you create another
feature branch or touch specs/ again later in the same session, these
conventions still apply.
