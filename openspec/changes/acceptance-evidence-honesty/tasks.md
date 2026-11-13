# Tasks: acceptance-evidence-honesty (#2288)

- [x] `scripts/check_pr_acceptance.py`: a ticked criterion citing `run=<id>` is judged by
      the run's LIVE conclusion and head (blocking `tick-cites-red-run`, blocking
      `tick-stale-head-unflagged`, blocking `tick-run-unreadable`, non-red
      `acceptance-proven-awaiting-writer`), with `--gh`/`--rev` threading.
- [x] `scripts/acceptance_writeback.py`: verdict-ref grammar floor (head sha required) +
      live green-run validation in the `writeback` command; `apply`/`check` stay offline.
- [x] `scripts/review_finalize.py`: validate `--verdict-ref` (green conclusion + head match
      against its live head observation) before calling `tick_acceptance`.
- [x] Tests: hermetic fake-`gh` run-lookup fixtures for every new finding class in
      `tests/test_check_pr_acceptance.py`; seam refusals in `tests/test_acceptance_writeback.py`
      and `tests/test_review_finalize.py` (existing refs updated, not just new tests).
- [x] Append-only audit addenda comments on the closed issues whose ticks cite red runs
      (the #2288 roster), never body edits.
- [x] Gates green locally: `make lint`, `make check-wiring`, `make openspec-validate
      NAME=acceptance-evidence-honesty`, the acceptance/writeback/finalize test files via
      the unit battery, `make lane-preflight`.
- [x] Issue #2288 body + PR body + commit text mirror the same ticked checklist; the PR
      carries `closes #2288`, `AGENTS:`/`BASE:` lines at the real shas.
- [x] Final verification: CI + ci-scope + ci-verdict green at the pushed head and
      `mergeStateStatus` not BEHIND (rebase + `--force-with-lease` if it is) before
      reporting the PR ready.
