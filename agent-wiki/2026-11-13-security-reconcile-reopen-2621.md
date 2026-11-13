# 2026-11-13 — the security reconcile reopen uses `gh issue reopen`, not a nonexistent `--state` flag (issue #2621, PR #pending)

- Problem: the daily security-scan reconcile leg reopened a merge-closed scan-evidence issue with
  `gh issue edit <n> --state open`, but `gh issue edit` has no `--state` flag, so every scheduled
  run that had to reopen a finding died at `cannot reopen #N: unknown flag: --state` (make target
  `security-issues-reconcile`, Makefile:1125, `scripts/security_issues.py:416`). Six consecutive
  daily runs red then aborted mid-batch — issues after the crash point never got their clearing
  comments.
- Fix: reuse the documented subcommand, `gh issue reopen <number>`, for the premature-merge-close
  reopen. `reconcile()`'s rc check (`returncode != 0 -> SystemExit`) is unchanged, so a failed
  reopen stays loud. `gh issue edit --body …` (line 478) and `--state` on `issue list` are correct
  as-is and untouched.
- Tests: `tests/test_security_issues.py::test_a_merged_pr_closes_never_clears_a_still_reported_scan_evidence_issue`
  now asserts the reopen argv is `["issue","reopen","9"]` and that no `issue edit` form appears in
  the reconcile leg. Targeted run rc=0 (19 passed).

Current status: implementation + tests written, uncommitted in the agent tree; full unit battery
and docs gates pending.
