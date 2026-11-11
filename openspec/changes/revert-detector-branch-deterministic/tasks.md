# Tasks — revert-detector-branch-deterministic (#2497)

- [x] 1. Create this OpenSpec change (`make openspec-new NAME=revert-detector-branch-deterministic`)
- [x] 2. Harness fix: `case_repo` inits with explicit `-b main` + `BASE_BRANCH=main`; the four base checkouts use `"$BASE_BRANCH"`
- [x] 3. Prove locally at the fix: named pytest test passes on this main-default host (1 passed, rc=0); old-shape harness reproduces the failure (rc=1, four `pathspec 'master'` errors)
- [x] 4. `make test-unit` green in a worktree carrying the fix (rc=0 at rebased head `7cfd1e8d2`; the unit job proves it again on the PR)
- [x] 5. Docs trio (`agent-wiki` note + `docs/changes.d` row + `CHANGES.md` via `make changes-index`), `make check-docs` rc=0
- [x] 6. Final verification: `make openspec-validate NAME=revert-detector-branch-deterministic` rc=0 (at `7cfd1e8d2`), `check_pr_closing` replay rc=0 and `check_pr_acceptance` replay rc=0 with `closes #2497` in tip commit + PR body carrying the issue's ticked criteria (both gates replayed green at `7cfd1e8d2`)
