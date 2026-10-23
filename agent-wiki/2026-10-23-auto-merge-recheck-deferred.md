# 2026-10-23 — a deferral is retried, not parked (#545)

**Issue:** [#545](https://github.com/asimov-agent/llgenie/issues/545) · **PR:** the PR that closes it

## What was wrong

`auto-merge` runs only on a completed `CI` run, and a deferral exits 0 by design. Nothing re-evaluated the PR
afterwards, so a blocker that cleared without a push left a green PR unmerged. Measured on #541: deferred at
06:05Z ("the author is the merge token's own account … or set APPROVER_TOKEN"), the secret added at 06:37Z, and
the merge only happened at 06:40Z because the run was re-executed by hand.

## What changed

- `scripts/auto_merge.py`: `deferred_for_head()` (the marker for exactly this head) and `recheck()`, which lists
  open PRs and re-runs the SAME `run()` for each one the gate deferred at its current head — bounded by
  `--max-prs`, skipping a stale marker or a PR with none. New `recheck` subcommand.
- `Makefile`: `make auto-merge-recheck REPO= [MAX=5] [DRY=1]`.
- `auto-merge.yml`: `schedule: */30 * * * *` + a `recheck` job using `BUMP_TOKEN` +
  `APPROVER_TOKEN`; the `merge` job remains `workflow_run`-only.

## Verified

- `pytest tests/test_auto_merge.py` in `llgenie/test:latest` → 41 passed (retried+merged, stale head skipped, no
  marker skipped, workflow wiring).
- `make lint`, `make check-docs`, `make check-wiring`, `make check-workflows`,
  `make openspec-validate NAME=auto-merge-recheck-deferred`, `make openspec-tasks-check` → green.
- `make test-unit` runs in the PR's checks.
