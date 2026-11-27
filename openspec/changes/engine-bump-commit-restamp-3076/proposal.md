# Change: restamp bump commit text before the lane pushes

## Why

Issue #3076: `scripts/engine_bump_restamp.py` (issue #3054) re-renders an open engine-bump PR's
BODY through the composer, but the lane's own COMMIT message was left with whatever acceptance
text the composer had at commit time. Measured residue: the `#3035` squash on `main` (`53a56da90`)
landed with three `PLACEHOLDER` proof clauses. Issue #3075 closed the reader side —
`check-pr-acceptance` and `check-pr-commit-checkboxes` now refuse stub-carrying `(proven: ...)`
clauses — but every bump wave still paid a manual amend dance to avoid a red lane.

## What Changes

- `scripts/engine_bump_restamp.py` gains a commit-text mode: it reads a commit MESSAGE file,
  replaces only its `## Acceptance:` block with the composer's measured `rc=0 run=<id>` clauses,
  and refuses to write if any draft stub survives. The subject and every non-acceptance paragraph
  are byte-preserved.
- `make engine-bump-commit-restamp` exposes the mode; the engine-bump workflow calls it between
  `git commit` and `git push`, amending in place when the message changed.
- The proof cites the workflow run id, not a head sha: a self-amending commit cannot name its own
  final sha, and a sha stamped before the amend would be stale at the live head (issue #2288).
  The PR body keeps the head-stamped clauses the composer already writes there.
- Hermetic tests cover stub replacement, block-less messages, per-variant image runs and the CLI's
  refuse-to-write path.

## Benefit

No bump wave pushes a stub-carrying commit message; the squash text that reaches `main` always
carries the measured proof, and issue #3075's refusal is a backstop nobody has to exercise.

## Not covered

- Reader-side gates (#3075) and the PR-body restamp leg (#3054) are unchanged.
- No engine bump is dispatched by this change; the next scheduled bump wave proves it in CI.
