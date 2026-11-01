# Verifying "green on merged main"

**"A run at the tip completed" is not "CI is green" — check the workflow name.**

After a merge, several workflows trigger at the new head. A `liveness` / `registry-liveness` run is
a single job and proves nothing about `linux / unit`. The acceptance criterion "merged result green"
means the real CI push run with the unit leg passing.

## Procedure

1. Resolve the actual current tip freshly: `git fetch origin +refs/heads/main:refs/remotes/origin/main`
   then `git rev-parse origin/main`. Never reuse a sha from a chat message or an older measurement —
   the tip moves under you (23f90235 -> 33ff24ff -> b91e11ca within minutes).
2. Find the CI run, not just any run, at that head:
   `gh api "repos/<o>/<r>/actions/runs?branch=main&event=push&per_page=10" --jq '.workflow_runs[]|"\(.name) \(.id) \(.head_sha[0:10])"'`
   and pick the entry whose `name` is the CI workflow at your sha. A `liveness` run at the same sha is
   a decoy.
3. Read the job list and the named leg by id:
   `gh api "repos/<o>/<r>/actions/runs/<id>/jobs?per_page=100" --jq '.jobs[]|"\(.name) -> \(.conclusion) (id \(.id))"'`
   Confirm `linux / unit -> success` by name and job id — not merely `run conclusion=success`.
4. An in-flight run is **pending, not green**. Poll to a terminal status before asserting.
5. Report run id + job id + main sha together, timestamped. A verdict with no sha is a claim about
   a branch that may no longer exist.

## API quirk

Workflow-run objects return `id` (not `database_id`); `--jq .database_id` yields `null` and silently
looks like a missing run. Use `.id`.
