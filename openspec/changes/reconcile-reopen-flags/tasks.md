# Tasks: reconcile-reopen-flags

## 1. The reopen call

- [x] 1.1 `scripts/security_issues.py` reopens with `gh issue reopen <n>`; no `issue edit --state` remains in the reconcile leg.

## 2. The test lock

- [x] 2.1 `tests/test_security_issues.py::test_a_merged_pr_closes_never_clears_a_still_reported_scan_evidence_issue` asserts the `["issue","reopen",...]` call shape and rejects any `issue edit --state` call; focused battery rc=0.

## 3. Verification

- [x] 3.1 `make lint` rc=0; `make check-docs` rc=0; the pair (`agent-wiki/` + `docs/changes.d/`) exists.
