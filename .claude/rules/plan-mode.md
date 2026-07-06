# Plan Mode & Approval

Every new feature MUST be developed inside Claude Code's actual plan
mode before any code is written — not just "treated like" a planning
step, but the real, tool-enforced plan mode (entered via Shift+Tab, or
by explicitly typing "enter plan mode" in the request).

This matters because plan mode is a genuine restriction, not just an
instruction: while it's active, file writes and state-changing commands
are mechanically blocked. That's a stronger guarantee than any written
rule, including this one — so the rule's job is to make sure plan mode
actually gets entered, every time, rather than relying on Claude to
remember to "act like" it's planning.

No exceptions for "this seems simple" — the developer decides that by
approving or rejecting the plan, not Claude.

## Process

1. Before any feature work begins, plan mode MUST be entered explicitly
   — via Shift+Tab, or by the developer/Claude stating "entering plan
   mode" at the start of the response. Do not propose implementation
   steps outside of plan mode.
2. Inside plan mode: if the feature is non-trivial (touches multiple
   files, has real ambiguity, or security/data implications) — write
   specs/<date>-<name>/spec.md first, using specs/\_TEMPLATE/spec.md.
   Surface open questions instead of guessing — ask the developer
   directly.
3. Once the spec (if any) is resolved, propose a plan: a concrete,
   numbered breakdown of the implementation steps. This proposal happens
   while still inside plan mode — no files are written yet because plan
   mode doesn't allow it.
4. STOP. Show the plan to the developer and wait.
5. The developer reviews and either:
   - Approves as-is → exit plan mode, proceed
   - Requests changes → stay in plan mode, revise the plan, show it again
   - Rejects → stay in plan mode, ask what to do differently
6. Only after explicit approval AND after exiting plan mode, create
   plan.md from the approved plan, with sections: To Do, In Progress,
   Completed.
7. Move to implementation.

## Mid-implementation ambiguity

If a genuinely new ambiguity surfaces during implementation — something
the upfront plan didn't and couldn't have anticipated (an unexpected
existing field, an edge case only visible once inside the code, a
decision the approved plan didn't cover) — stop and ask the developer
directly before proceeding on that specific point. Do not silently
guess and continue, even if implementation is otherwise mid-flow.

This does not mean re-entering plan mode or re-approving the whole plan
— it's a targeted question about the one ambiguous point, answered
inline, after which implementation continues from where it paused. Only
fall back to a full new plan-mode cycle if the answer meaningfully
changes the scope of the feature itself.

## Rule

Never skip straight from a feature request to writing code, and never
propose a plan outside of actual plan mode. The plan-mode-entry step,
the proposal, and the approval are all mandatory — none are optional
even under time pressure, regardless of stack or team size.
