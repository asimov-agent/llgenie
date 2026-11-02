# worktree-base-origin-main — Tasks

Issue: [#845](https://github.com/asimov-agent/llgenie/issues/845)

- [x] 1. `scripts/worktree_base.py` resolves the worktree base from `refs/remotes/origin/main`, fetching `origin main` first; `make worktree-base` wires it; `tests/test_worktree_base.py` proves a worktree cut while the primary checkout is parked on a PR branch lands on `origin/main` (criterion 1). Verified: 3/3 tests pass in llgenie/test; `python3 scripts/worktree_base.py resolve` returns origin/main@4e533896.
- [x] 2. `bot_preflight.py` records `BASE: <sha> (== origin/main at open)` beside the `AGENTS:` line; `tests/test_bot_preflight_base_line.py` locks it (criterion 2; gate half in task 3). Verified: 3/3 tests pass.
- [x] 3. `check-pr-base` gate fails a PR whose merge-base with `refs/remotes/origin/main` is not `origin/main` itself, naming the foreign commit; negative control stays green; `tests/test_check_pr_base.py` covers both (criteria 3 and 5). Wired into ci-unit roster + DEFERRED in issue_bot_gates + a guard-job step in ci.yml. Verified: 4/4 tests pass; `make issue-bot-gates-check` green; `make check-pr-base` green on this branch.
- [x] 4. `worktree_report.py` reports the primary checkout's branch, ahead/behind count and uncommitted paths; `tests/test_worktree_report_drift.py` pins it (criterion 4). Verified: 3/3 tests pass.
- [x] 5. `make openspec-validate NAME=worktree-base-origin-main` exits 0; every task above ticked; `make check-wiring` and `make issue-bot-gates-check` green. (`make lane-preflight` runs after the commit so it describes the pushed tree.)
