# Proposal: reconcile-reopen-flags

## Why

`scripts/security_issues.py`'s reconcile leg reopens a merge-closed scan-evidence issue
whose finding is still reported with `gh issue edit <n> --state open`. `gh issue edit` has
no `--state` flag: the call exits 2, `reconcile()` raises SystemExit, and `make
security-issues-reconcile` dies mid-batch. The daily security-scan workflow has failed 6
consecutive scheduled runs (2026-11-07 … 12) through this crash (run 43216472585 log:
`cannot reopen #2467: unknown flag: --state`), and every clearing comment after the crash
point in the batch is lost that day.

Issue: #2621.

## What Changes

- `scripts/security_issues.py`: the reopen call becomes `gh issue reopen <n>` (the real
  subcommand); the loud-failure check is unchanged.
- `tests/test_security_issues.py`: the existing merge-close/reopen test is updated to lock
  the new call shape and to forbid the invalid `issue edit --state` form.

## Impact

- `make security-issues-reconcile` (Makefile:1125) and the daily `security-scan.yml` job go
  green once the two real findings fixed by #2608/#2610 stop being reported.
