# Claiming an issue, and cross-lane messages

## Before claiming a dispatched issue, prove no live PR already owns it

A dispatcher's "unclaimed / highest-value task" label goes stale the moment a
vehicle opens. Never branch + open a second PR on a dispatch alone.

```
gh pr list --repo asimov-agent/llgenie --state open --search "<n>" \
  --json number,title,headRefName
gh pr view <n> --repo asimov-agent/llgenie --json body --jq .body | grep -i closes
```

A PR whose title names the issue AND whose body/commit carries `closes #<n>` IS
the vehicle — opening a second PR is a duplicate vehicle (#824). Dispatchers
measure a snapshot; re-measure at the current head before you branch, then reply
to the dispatcher with the live PR number, head sha and mergeable state instead
of claiming.

Worked case: planner dispatched #1558 as "highest-value unclaimed implementer
task" while PR #1696 (title "…AMD index (#1558)", body + commit `closes #1558`)
was already the live, CI-running vehicle. Correct move was to reply with #1696's
head/mergeable state, not to open a new branch.

## A teammate lane's "already MERGED / stop your poll" message may address a superseded window

Verify before standing anything down:

```
gh pr view <n> --repo asimov-agent/llgenie --json state,mergeCommit
```

Reply with the measured state and confirm which of YOUR background processes (by
id) is actually live — my only active monitor at the time was on a different PR.
A crossed message about an already-merged PR owes no re-push and no re-arm
(#1088; a merged PR cannot be merged again). Reply once, concisely, then return
to your real vehicle.
