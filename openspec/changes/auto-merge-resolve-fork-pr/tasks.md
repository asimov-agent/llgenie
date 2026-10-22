# Tasks — auto-merge-resolve-fork-pr

- [x] 1. OpenSpec change
- [x] 2. `scripts/resolve_run_pr.py`: run object first, owner-scoped head search second, digits-only values,
      loud failure when nothing resolves, `number=<n>` written to `$GITHUB_OUTPUT` (or printed)
- [x] 3. `Makefile`: `auto-merge-resolve` target (the one code path) + `.PHONY` entry
- [x] 4. `.github/workflows/auto-merge.yml`: the resolution step calls that target, inline shell removed
- [x] 5. `tests/test_resolve_run_pr.py`: real resolver against a real fake `gh` binary, plus the workflow-text
      assertion
- [x] 6. README + agent-wiki
- [x] 7. Verified: `pytest tests/test_resolve_run_pr.py` → 7 passed; the old inline step reproduced the
      measured multi-line `$GITHUB_OUTPUT` blob against the same fake `gh`, the new target writes `number=506`
