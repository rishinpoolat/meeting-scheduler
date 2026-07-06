# Project Name

One paragraph: what this project does.

## Commands

- `<fill in>` — start dev server
- `<fill in>` — run tests
- `<fill in>` — typecheck
- `<fill in>` — lint

> Fill these in from the project's actual package manifest (package.json,
> pyproject.toml, go.mod, etc.) once it exists. Until then, leave the
> placeholders — don't guess a stack that hasn't been chosen yet.

## Architecture

See @CODEBASE_MAP.md for folder-by-folder layout. Read it before
grepping — it should answer "where does X live" faster than searching.

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

- (fill in: linting/formatting specifics not already enforced by tooling)
