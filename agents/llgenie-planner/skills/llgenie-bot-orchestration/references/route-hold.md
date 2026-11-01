# Route-hold: never route a PR to the reviewer mid-CI

A PR can show `holds` and `ci-scope` = SUCCESS while the deciding `CI` row is still `in_progress`. Routing to the reviewer at that point is a race: a leg that greens the diff can flip the PR dirty *after* the route is dispatched, and the reviewer then measures a head that no longer matches.

## Rule

- **Route on completed-success only.** `gh api 'repos/<owner>/<repo>/actions/runs?head_sha=<head>' --jq '[.workflow_runs[]|{name,status,conclusion}]'` — every row must be `status=completed, conclusion=success`. A single `in_progress` or `null` conclusion = hold; post a route-hold comment on the PR and wait.
- **Arm on the same green.** A push is the trigger — but only once the rollup is completed-success. Read the arm back: a null REST `enabled_at` means NOT armed even though `gh pr merge --auto` exited 0 (#964).
- **A lane's prose "routed to the reviewer" is not a fact.** The fleet has no in-repo reviewer workflow; routing is the planner's dispatch. Before assuming a self-route happened, confirm `gh api repos/<o>/<r>/pulls/<n> --jq '{review_requests:[.requested_reviewers[]?.login],review_decision}'` returns empty and the labels are unchanged. Empty = nothing was routed; the hold stands.
- **Correct a lane's stale head in the route-hold comment**, but separate substance from bookkeeping: a fold that is byte-identical at the real head passes even if the lane misstated the base sha (base is `base.sha`, resolved from `baseRefName`, never the lane's quoted main).

## What a route-hold comment says

Name the head sha you held at, the exact rows that were green vs still running, that routing waits for completed-success, and that the PR is not armed (owner gate, #964). That comment IS the vehicle's state; a lane reading the PR sees the hold and does not self-route.
