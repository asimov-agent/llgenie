# One branch, one owning lane

## The failure

A PR's CI went red with a procedural gate failure (a `# proc-allow:` marker on the wrong line).
The planner diagnosed it exactly and dispatched the one-line fix to a second lane — while the
branch's owning lane was still actively pushing to the same branch. The owning lane landed the
fix first. Two lanes briefly held write intent on one ref.

Nothing was lost, but only because the owning lane happened to win the race. Had both pushed,
the later push would have been a force-or-reject against a branch it was not dispatched for.

## Why it happens

A red CI job looks like *work*, and the planner's instinct is to route work to the lane whose
*specialty* matches the failure (a pipeline gate failure -> pipeline maintainer). But specialty
is not ownership. The lane that opened the branch owns it, and a gate failure inside a PR is
the PR author's to fix, not the gate-maintainer's.

## Rule

**Before dispatching a fix to an existing branch or PR, establish who pushed the last commit.**

- `gh api repos/<o>/<r>/pulls/<n>/commits?per_page=10` — read the newest commit's author/committer
  and timestamp. If it is minutes old, the owning lane is live.
- `gh api repos/<o>/<r>/pulls/<n>` — check `head.sha` and `head.ref`; a head that has moved since
  the dispatch you are about to write supersedes it.

If the owning lane is live: dispatch nothing. Send it the diagnosis and let it push.
If the owning lane is idle or wedged: dispatch, and say explicitly that it now owns the branch.

## When the collision has already happened

Correct it out loud, and name the error as the planner's — not the second lane's:

1. Message the lane you wrongly dispatched: state that the branch is read-only for it from now on.
2. Tell it what actually happened (head sha, who landed the fix) so it does not re-push from a
   stale local copy.
3. Record the same on the PR thread.

A second lane that pushed where it was told to has not misbehaved; an orchestrator that told two
lanes to touch one ref has.

## Related

Specialty routing still applies for *gate construction* (fixing the rule, not the PR). A gate that
is itself wrong is the maintainer's; a PR failing a correct gate is the author's.
