# Queue depth: subtract the parked families before you count work

A sweep that counts *unassigned, branchless* issues as "available work" overstates the queue and
misroutes lanes. Most of a real board's unassigned rows can be unreachable for one shared reason.

## The sweep, in order

1. **Enumerate** open `agent:implement` issues (paginate; do not stop at the first page).
2. **Mark rows that already have a vehicle**: a matching branch (`issue-<n>`, `fix/<n>-*`) or an open
   PR whose body closes the issue. These are in flight, not available.
3. **Mark rows a lane already holds**: a live `bot-claim:` comment, or an assignee.
4. **Classify the remainder into dispatchable vs parked** — this is the step that gets skipped.

## The parked test

An issue is **parked**, not dispatchable, when executing it would fail for a reason the lane cannot
fix. The dominant case in a gated repo:

- The issue is a *manual-dispatch verification* ticket (`ci(verify)`, "prove <workflow> works via manual
dispatch") and the workflow it dispatches is `disabled_manually`. Dispatching it yields the same 422 and
the same wasted run every time.
- The issue's acceptance names a gate that is currently red for a cause tracked elsewhere.
- The issue needs an owner action (a credential, a workflow re-enable, a protected-setting change).

Read the blocker's own state before classifying: `gh api repos/<o>/<r>/issues/<n>` for `state`,+
`gh api "/repos/<o>/<r>/actions/workflows/<wf>/runs?per_page=1"` (or the workflow list) for whether the
dispatch target is actually enabled.

## Report the queue as two numbers, never one

State `dispatchable=N` **and** `parked=M behind <blocker>`. A bare "31 unassigned issues" is a false
board reading: it makes an idle fleet look like it is declining work that exists.

## Then mutate the blocker's thread

The highest-leverage planner action when a whole family is parked is not dispatching any of them — it
is a single quantified record on the blocker's issue:

- how many open tickets the blocker parks (name them by number, or name the family and the exact rows
you measured);
- the failure the dispatch would produce (name the error, not "blocked");
- why it has stayed open (small individual tickets read as scheduling noise, not as one owner-gated
  blocker);
- the concrete ask, and the alternative if the owner declines (label them `parked` with a date so the
  filter stops returning them as available).

That comment converts an invisible repeated cost into one decision. It is also a legitimate, in-authority
mutation to land when a progress guard fires and nothing else is genuinely owed.

## Idle-capable lanes: a parked queue is not an empty queue

A lane whose reactive queue is entirely parked still has work — its own domain audit. When the sweep
turns up exactly one gate-free item in a lane's domain (a continuous-improvement tracker, an untracked
alignment/freshness/coverage gap), dispatch *that*, and say on the issue why the rest of the queue is
parked so the next reader does not re-derive it.

Order the choice by cost, not by the ticket list: one dispatch that fills an idle lane beats ten parked
tickets that would burn ten runs.
