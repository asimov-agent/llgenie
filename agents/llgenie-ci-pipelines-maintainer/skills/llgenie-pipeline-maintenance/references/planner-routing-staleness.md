# Planner routing arrives stale — re-measure before you act

`@llgenie-planner` (inbox triage) routinely dispatches on a snapshot older than the
board. It will assert an issue is "open / unclaimed / live" and a PR head is "c63e13ab"
long after that issue was merged shut and the head advanced. Treat every routing message
as a *hypothesis to verify at the API*, never as fact.

## Before acting on any dispatch

1. `gh issue view <n> -R asimov-agent/llgenie --json state,stateReason,closedByPullRequestsReferences`.
   If it is `CLOSED/COMPLETED`, do not open a duplicate vehicle and do not re-claim it —
   say so, once, with the closing PR number and sha. A closed-by-my-own-merged-PR issue is
   finished; re-filing it is a duplicate-control defect.
2. `gh pr view <n> --json headRefOid,mergeable,author,isDraft`. The head the planner quotes
   is often stale; measure the live `headRefOid` before judging ancestry or red state.
3. For a claimed "live main-red", check the *current* main head's run, not the run at the
   sha the planner cites. The red it anchors on is frequently a pre-merge sha that a later
   fix already absorbed: `gh run list --workflow ci.yml --branch main --limit 3 --json
   databaseId,conclusion,headSha`. If the current head's run is `success`, there is no live
   red and nothing to file.

## Lane boundaries the dispatch will try to cross

- A stale-head PR (base behind main, `MERGEABLE`, the fix sha not an ancestor) is a **rebase**,
  which belongs to `@llgenie-pr-merge-conflict`, not this lane. Route it there with the live
  head + current main sha + the `merge-base --is-ancestor` rc; do not push into it yourself.
  (owner instruction 2026-10-30)
- Label CRUD is planner board-state. When an issue's labels are wrong, file a request;
  do not self-mutate labels — that caused a "label doesn't exist / now exists" correction.

## How to answer a repeated stale dispatch

Do not loop a seventh "it's closed" reply. Settle it with a *new measurement*: the current
main run's conclusion, or the live PR head. One evidence-backed message (issue state +
closing sha, or current-head run id + conclusion) ends the loop better than repeating the
same assertion. Quote the sha/run id you measured and the timestamp, so a stale rerun is
self-evidently pre-merge.
