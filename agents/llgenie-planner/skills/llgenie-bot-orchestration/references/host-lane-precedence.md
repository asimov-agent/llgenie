# Host-lane working takes precedence over CI machinery (owner rule, 2026-11-08)

The owner's directive, verbatim in substance (2026-11-08, #2073): *"your own behaviour for
working with your bots should always take precedence on the host.. the CI is just the CI
really"*. The fleet's hands are the **host lanes**; the CI workflows are **support**. A pass
reaches for the owning host lane FIRST and treats CI only as the thing that reports red —
never as the thing the planner repairs.

> **Host-lane working always takes precedence on the host. The CI workflows are support, not the
> subject.**
> A pass reaches for the **owning host lane first**. CI is only the thing that reports red — never
> the thing the planner repairs. A red CI job is *evidence*, and the response to evidence is a
> dispatch to the lane that owns the action, not planner-side work on the pipeline.

## The precedence chain on every pass

1. **Host lane owns it → dispatch it** (the ownership map below).
2. If an in-repo CI bot declines or is blind → **still step 1**: dispatch the host lane, and file
   the CI defect as its own issue for the code lane (the two-trail rule below).
3. **The planner never repairs the CI bot itself.** A branch, commit or code change from the
   planner is a defect. The planner only files issues and dispatches (SOUL: "You do not implement").

## Ownership map — the answer to "which host lane owns unblocking this PR?"

Recorded where the planner reads at dispatch time:

| work class | owning host lane |
|---|---|
| rebase / force-push / conflicted `DIRTY` PR | `llgenie-pr-merge-conflict` |
| product code | `llgenie-issse-implementer` |
| docs | `llgenie-documentation-maintainer` |
| workflow / gate / script | `llgenie-ci-pipelines-maintainer` |
| engine / serving | `llgenie-engine-improver` |
| test evidence | `llgenie-tester` |
| review verdict | `llgenie-pr-reviever` |

This is the same ruling as section **2b. Route to the bot that owns the work class** in the
orchestration SKILL.md, applied as a precedence rule: when a PR is unblocked by a host action, the
host lane that owns that action does the work — never the in-repo bot that merely reported it.

## "The automation refused" is a trigger for host-lane dispatch, never planner-side repair

A PR the automation declines (a stale-base PR the sweep prints `BLOCKED against main` for, a PR
the fix-bot refuses, a label an in-repo bot cannot set) is unblocked by the **host lane that owns
the action**, on the first pass. Measured failure this rule prevents (2026-11-08, #2073): six
PRs stale-base — the planner dispatched `rebase-bot.yml` (`42438486613`, `rebased: 0`), then
diagnosed `scripts/rebase_bot_sweep.py` locally, then churned issue-bot labels — before finally
dispatching `@llgenie-pr-merge-conflict`, which should have been the first and only action.

The rule: **when an in-repo bot declines a PR, the host lane that owns that action does the work;
the in-repo bot's defect is filed as an issue and left to its own lane.** Before any in-repo bot
is re-dispatched, answer "which host lane owns unblocking this PR?" and dispatch it.

## Two trails, kept separate

A declined automation job produces EXACTLY two artifacts when the automation is also blind:

1. **One issue in the owning code lane for the defect** — e.g. #2071 owns the `rebase_bot_sweep.py`
   blindness (`BLOCKED` masking `BEHIND`). The planner files it; it does not restate or implement it.
2. **One host-lane dispatch (plus an on-PR anchor) for the unblock** — the owning host lane gets the
   `message_agent` with the PR list and the unblock, and the instruction is anchored on the PR so it
   survives a full mailbox (`references/dispatch-and-handoff.md`).

Never fold the two: the defect issue stays in its owning code lane, the unblock dispatch stays on
the PR. A pass that mixes them produces a duplicate or misplaced trail and looks busy while the
board does not move.

## What the planner never produces on this path

AC5 (this issue's acceptance): no planner-authored branch, commit or code change is ever produced
by this path. The unblock is a dispatch, the defect is an issue; both are written homes, neither is
a write to the tree.

## Versioning

This rule lives in the planner profile's orchestration skill. Versioned as a PR under
`agents/llgenie-planner/` per #791 — never edited privately on the host. (SOUL edits are the
protected-file wall; a rule change lands by issue + PR.)
