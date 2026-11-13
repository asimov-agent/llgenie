# security-issues reconcile: reopen via `gh issue reopen`, not `gh issue edit --state`

Issue: #2621. PR: #2622.

## What was wrong

`scripts/security_issues.py` reopened a merge-closed scan-evidence issue whose finding was
still reported with `gh issue edit <n> --state open`. `gh issue edit` has no `--state` flag,
so every such reopen exited 2 and `reconcile()` raised SystemExit. The daily security-scan
workflow (398132862) failed 6 consecutive scheduled runs (2026-11-07 … 12): run
43216472585 died at `cannot reopen #2467: unknown flag: --state` (Makefile:1125),
aborting the batch mid-list so later genuine clears never got their comments.

Two of the six reds were also REAL findings (containers/test DS-0002, relay.mjs
spawn-shell-true) — those were fixed and merged via #2608 and #2610.

## The fix

`scripts/security_issues.py`: `["issue", "reopen", str(number)]` — the real subcommand.
The loud-failure check is unchanged. The existing test
`tests/test_security_issues.py::test_a_merged_pr_closes_never_clears_a_still_reported_scan_evidence_issue`
was updated (not duplicated): it now locks `["issue","reopen",<n>]` and rejects any
`issue edit` call carrying `--state`.

## Verified

- Focused battery in the hermetic container: `pytest tests/test_security_issues.py`
  → 19 passed, rc=0 (post-fix tree).
- `grep -rn 'edit.*--state open' scripts/ tests/` → no remaining call sites.
- `gh issue reopen --help` answers on this host (the subcommand exists).

## Current status

PR #2622 drives the change; the next daily scheduled security-scan run on fixed `main`
should complete success — the verdict findings from run 43216472585 are already gone from
`main` (trivy 0 misconfig after #2608/#2617, semgrep spawn-shell-true gone after #2610).
