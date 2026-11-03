# LLGenie Pipeline Maintainer: the ci-frozen-reaper collapses a run stuck `in_progress` (#1679)

Implements issue #1679 (ready-for-review PR, never merged). A GitHub Actions run that hangs
`in_progress` (job never advances) is invisible to BOTH existing healers: `ci-requeue` re-runs only
**cancelled** runs, and `run-failure-reactor` fires only on `conclusion: failure`. A frozen
`in_progress` run matches neither predicate, so it blocks the PR verdict indefinitely until a human
intervenes. Observed on #1671: an old head 9114c706 with a `linux/unit` job stalled `in_progress`
while check-pr-base had already flagged the branch at a stale base; neither healer could touch it.

## What changed (measured on this worktree, main `2d9d9457`)

- `.github/workflows/ci-frozen-reaper.yml` — a third, time-bounded healer: own schedule
  (every 2 hours — minute 19 on six weekdays + minute 27 on Monday, the only odd collision-free
  all-day non-every-hour shape, issue #275/#301) + `workflow_dispatch`, never a
  `pull_request`/`push` trigger. Runs `make ci-frozen-reaper`, which calls
  `scripts/ci_frozen_reaper.py run`.
- `scripts/ci_frozen_reaper.py` — lists `in_progress` runs, and collapses ONLY one whose
  `updated_at` is older than the threshold (default 90m) **and** whose run age exceeds the 15m grace
  **and** that has an OPEN pull request at its head. It posts the evidence comment (run id, both
  timestamps, PR, named owner) to the PR thread BEFORE cancelling, then `gh run cancel` +
  `gh run rerun` for that one run. `plan` / `--dry` prints and touches nothing. It NEVER touches a
  run still advancing (fresh `updated_at`), a run younger than the grace, or a push/schedule run (no
  open PR = not a PR verdict). This is the #817 boundary honoured: never cancel a live run to clear
  the queue — only a run frozen past the threshold on an open PR.
- `Makefile` — `ci-frozen-reaper:` target (THRESHOLD=90m, DRY=1 previews) mirroring
  `ci-requeue-cancelled`; added to `.PHONY`.
- `tests/test_ci_frozen_reaper.py` — 8 tests: the frozen-on-open-PR collapse (evidence-before-cancel
  asserted), the advancing run left alone, the grace-period run left alone, the no-open-PR run left
  alone, `--dry` preview, threshold-mixing, the parser refusing garbage, and the wiring test that
  pins the cron/`workflow_dispatch`/concurrency/permissions/`make` target/pinned-actions.

## Verification (measured, not asserted)

- Container run (`llgenie/test:latest`, `PYTHONPATH=/repo/scripts`):
  `pytest tests/test_ci_frozen_reaper.py -q` → **8 passed**.
- Extended to the adjacent wiring (`test_ci_requeue.py` etc.) after wiring the Makefile and workflow.
- The evidence-before-cancel ordering is asserted by the fake-`gh` argv: the `issues/<n>/comments`
  POST precedes the `run cancel` in the recorded call sequence.
