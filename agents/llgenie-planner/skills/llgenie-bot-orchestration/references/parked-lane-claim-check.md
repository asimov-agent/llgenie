# "Parked awaiting dispatch" is an unverified claim

A lane that has just finished a merge wave routinely reports "nothing has been dispatched to me,
0 open PRs, parked" while its own `bot-claim:` comments still sit on open issues. Treat the self-report
as a claim about the lane's memory, not about the board.

## The check

1. Pull the lane's claim trail per issue:
   `gh issue view <n> --json comments --jq '[.comments[]|select(.body|test("bot-claim";"i"))|.body]'`
2. Read the ordering each claim states (`QUEUED behind #A → #B → #C`, and any later
   "QUEUE CORRECTION" comment — the newest correction wins).
3. Resolve the predecessors: `gh issue view <n> --json state,closedAt`; for issues that shipped as a PR,
   confirm the merge sha and that the branch is gone (`gh pr list --head agent/issue-<n> --state all`).
4. The first predecessor still OPEN is the live frontier. Dispatch the lane onto it, citing the fresh
   `origin/main` sha, the issue id, scope, out-of-scope, and what "done" means.

## Why it matters

"The lane says it is parked" and "the lane has no work" are different facts. Only the second justifies
leaving a lane idle; the first means a dispatch was forgotten. The inverse error is just as costly —
inventing a fresh assignment from the open-issue list when the lane already holds a refined, claimed
issue produces two vehicles on one problem (#824).

Also re-read for a **queue correction** comment: a rescheduled frontier (#1464 dropped as mis-routed)
supersedes the original claim's ordering, and dispatching against the old order re-creates the mis-route.
