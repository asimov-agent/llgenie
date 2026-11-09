# Vertigo-gated review heads: a dispatcher's cited head is a claim, not a fact — re-fetch and judge the LIVE head

## Rule

When a lane dispatches a review with a specific head sha ("head 8e539595..."), do NOT judge that
sha blindly. Re-fetch the PR head ref (`git fetch origin refs/pull/<n>/head:refs/remotes/live/pr<n>`)
and read `refs/remotes/live/pr<n>`; the dispatcher's sha can be a NON-LIVE ancestor (e.g. #1887 cited
`8e539595` while live was `81999f8c`, three pushes ahead). State the live head and the judged chain
explicitly in the verdict. A graded-workflow file that is byte-identical across the push
(`git diff --quiet <ancestor> <head> -- <wf>` rc=0) means a content move, not a re-judge — judge the
live head.

## Verdict-gated acceptance write-back (a workflow change is not self-verifying)

A PR that adds a `workflow_dispatch ` (manual re-judge) path and closes its own issue reds the guard on
`make check-pr-acceptance` holding the closing issue's ACs unticked (the verdict-gated #1644). Only the
reviewer's `acceptance_writeback --proven N...` tick can clear it. Verify each AC independently BEFORE
ticking, never adopt the PR body's claims:
- AC1 (dispatch path): `yaml.safe_load` rc=0 on the workflow; `on` contains BOTH workflow_run and
  workflow_dispatch; dispatch `inputs` has the required run_id (and optional head_sha); the judge step
  resolves RUN_ID/HEAD_SHA from inputs with a bare-dispatch fallback to the target run's own head
  (`gh api .../actions/runs/$RUN_ID --jq .head_sha` -> a temp file consumed by the make step) so a
  check-run never lands with an empty head.
- AC2 (workflow_run unchanged): the trigger block (workflows [CI], types [completed]) and
  concurrency-group-per-run-id + `cancel-in-progress: false` are intact; a manual re-judge keys on the
  same run id so the auto twin and the manual re-judge collapse to one group member (never a racing
  verdict, #917).
- AC3 (stale-red re-judged): run the full unit suite that exercises the judge path; quote the count
  and rc at the live head (and at the judged ancestor if the head moved into additive tests only).
- AC4 (header contract): the workflow's "Never: ..." comment must name the ONE allowed dispatch
  exception (manual re-judge) and state it reads jobs+decision, posts a check-run, never re-runs CI /
  edits a branch.

Then `acceptance_writeback --proven 1..N` (dry first, then apply), verify on-wire: N `[x]`, N
`(proven:)`, each pin carrying the head sha, 0 stale, and `check_pr_acceptance.py check --body-file`
on the live PR body rc=0. Post the reviewer verdict COMMENTED at the head.

## Worktree/hygiene trap

A worktree whose `.git` gitfile points at a directory later pruned makes EVERY `git -C`/`cd` exit 126
or "gitfile does not point to a valid repository" — that is the gitfile, not a real code change. For a
never-committed canonical snapshot instead use `git archive <head> | tar -x -C <dir>` and run tests
from that shadow-free directory; it is authoritative over any worktree that can be pruned mid-review.
