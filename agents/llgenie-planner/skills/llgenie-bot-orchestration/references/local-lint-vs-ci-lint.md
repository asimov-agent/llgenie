# Local lint is not CI lint (llgenie `scope` gate)

## Rule

A lane reporting "LINT OK" / "`make ci-lint` passes" proves nothing about files it has not committed yet.

The `scope` job's trailing-newline gate (`lint_linefeeds.py`, the #1539/#1543 gate) walks **git-tracked** files only. A new file that is still untracked (or exists only in the working tree) is skipped, so the gate passes locally and reds `scope` on CI after the push.

## Verified failure shape

Observed twice on the same vehicle family:

- PR #1545 round 1 — 4 added files missing trailing newline, `scope:FAILURE`.
- PR #1548 round 1 (head `62acdbb9`) — 5 added files (agent-wiki note, `changes.d` fragment, openspec proposal/spec/tasks) missing trailing newline, `scope:FAILURE`, while the lane had reported lint green.

Both times the author's explanation was the same and correct: lint ran before the files were staged, so they were invisible to the gate.

## What the planner does with a lane's lint claim

1. Do not accept "lint OK" as evidence when the PR's new files were added in the same round.
2. Read `statusCheckRollup` at the pushed head — `scope` pass/fail is the fact, not the local report.
3. On a `scope` red, name the exact files in the fix dispatch (parse the job log's file list) instead of saying "lint fails".

## Instruction to carry into fix dispatches

"Stage or commit the new files first, then run `make ci-lint` — the gate only sees tracked files."
