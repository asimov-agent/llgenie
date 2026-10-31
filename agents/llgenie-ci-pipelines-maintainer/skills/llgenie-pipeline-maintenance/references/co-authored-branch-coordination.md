# Co-ordinating on a shared single-PR branch

When two lanes land BOTH halves of one change on ONE PR, the branch is a shared
mutation: the head advances by a commit each time the other lane pushes, and any
plan you prepared earlier is stale the moment the other lane moves.

## The rule

Re-fetch and re-read the PR's file list before EVERY push of a prepared delta.

1. `git fetch <remote> <branch>` — never push against a head you named in an earlier
   circuit.
2. `gh api repos/<o>/<r>/pulls/<n>/files --paginate --jq '.[].filename'` — check each
   file you planned is NOT already on the branch.
3. A delta whose files are already there is **superseded** — reconcile with what is on
   the branch, or abandon the piece. Never re-add it.

## Why

A peer may already have committed the very files you prepared. Pushing your copy then
CONFLICTS, or resurrects a workflow the other lane deliberately removed (measured: an
`published.yml` removed + `ci.yml` engine jobs cut + tests re-pointed, while a desk
plan still carried a delta for those files). Pushing a stale delta on a co-authored
branch is how an orphaned workflow comes back and a green gets a second, conflicting
copy.

## An owner direction can supersede the whole plan mid-flight

"Remove engine build/test entirely" supersedes "reduce the tag poll" — a scope change
updates what the branch should carry. Re-verify what the branch now carries BEFORE
matching your old plan to it, and say plainly that the earlier plan is superseded,
rather than piling the old delta on top of the new shape.

## When a peer announces a change of scope

Trust but verify read-only: re-fetch the shared branch and confirm the reported state
(commit list, files present/removed) before you reply "the branch is baseline now"
or "my delta applies". A stale claim forwarded during a live multi-lane cut is how a
coordinated merge becomes a conflict-by-hand.
