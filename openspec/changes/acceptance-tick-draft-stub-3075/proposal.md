# Proposal: acceptance-tick-draft-stub-3075

## Why

Engine-bump squash commits landed on `main` carrying `PLACEHOLDER` proof clauses: `main@53a56da90`
(PR #3035) has 3 lines shaped `(proven: … rc=0 PLACEHOLDER)` / `(proven: rc=0, engine-build run at
head PLACEHOLDER)` (measured 2026-11-26 via `git log origin/main -12 --format='%h %s%n%b' | grep -n
PLACEHOLDER`). The tick readers are stub-blind: `check_pr_acceptance._is_provable_tick` accepts any
`(proven: …)` clause carrying `rc=` plus a 7-40-hex token — a blob sha satisfies it — and
`check-pr-hygiene commit-checkboxes` checks only that the commit-text tick exists. A lane that stamps
draft proof text and skips the stamp replacement is CI-green, so the stub reaches `main` and the
squash text stops being evidence (issue #745's mirror rule). Issue: #3075.

## What Changes

- **ADDED**: `check_pr_acceptance` refuses a ticked criterion whose `(proven: …)` clause carries a
  draft stub token (`PLACEHOLDER`, `HEADSHA`, `MAINSHA`) — the tick reports unproven instead of
  passing on a blob sha.
- **ADDED**: `check_pr_hygiene commit-checkboxes` refuses a ticked `- [x]` commit-text mirror line
  whose `(proven: …)` clause carries the same draft stub tokens.
- **ADDED**: test cases in `tests/test_check_pr_acceptance.py` and
  `tests/test_pr_hygiene_commit_checkboxes.py` pin both refusals, built from the exact `#3035`
  residue clause shapes.

Not changed: the already-landed `53a56da90` text (no history rewrite), the tick write-back seam
(#1644), or the PR-body restamp seam `scripts/engine_bump_restamp.py` (issue #3054) — the refusal
is the fix; the lane supplies the real proof. Auto-rewriting draft stubs in the lane's own commit
text (a commit-text mode for that restamp seam) is filed as issue #3076.
