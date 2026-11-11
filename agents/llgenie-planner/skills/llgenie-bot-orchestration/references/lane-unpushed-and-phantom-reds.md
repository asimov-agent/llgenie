# Lane "local/unpushed" claims and phantom-red loops

Two recurring reconciliation traps when a lane reports state you did not measure yourself.

## A lane's "local-only / push held" claim is the one most often already false

A lane working from a degraded or stale local snapshot reports commit X as "local, push held"
when X is in fact already on the remote branch — often with a newer head already pushed on top of
it. Never force-push, and never tell a lane to push, on that premise. Settle it from the remote:

- `gh api repos/OWNER/REPO/pulls/<n>/commits` — what is actually on the branch (newest first).
  If both X and a newer head H appear, X is already pushed.
- `gh api repos/OWNER/REPO/compare/<X>...<H>` returning `ahead=1,behind=0,status=ahead` proves X
  is an ancestor of the live head H (the head is exactly one commit on top of X).
- `gh api repos/OWNER/REPO/git/trees/<H>?recursive=1` and `pulls/<n>/files` — if the pushed head's
  tree already carries the files the lane says are missing/uncommitted (`status:"added"`, absent
  from base), the fix is landed. Report that and hold; block any re-push over a correct head.

A degraded lane channel is exactly how this happens — the lane "sees" a stale snapshot and
concludes "my commit is local". Your answer cites the remote shas, not its local view.

## Phantom-red loops: a lane re-refuting a red you never cited

Intermediate heads (`020345e0`, `6cadd0b6`, `f4a97e68`, …) surface because another lane
(ci-pipelines, rebase) sampled the PR at an earlier moment. They are that lane's reads — not a
planner dispatch and not a planner assertion. When a lane keeps "correcting" a red at such a head
"that you cited", it is re-refuting a phantom instruction: a ghost-loop.

Do not run a fresh verification round each time it recurs. Send ONE consolidated loop-breaker:
state that the sha was another lane's intermediate read, name the live head and its verified gate
state, keep it short, and stand. A lane that re-refutes the same phantom twice is the ping-pong
you are meant to stop — correcting the misattribution once ends it; repeating the correction
re-feeds it.
