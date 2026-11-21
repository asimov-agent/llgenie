# Tasks: stalled-job-watchdog-2992

## 1. Change and issue

- [x] 1.1 Open the OpenSpec change (proposal, spec delta, tasks) before any code, referencing issue #2992 and its measured run `44863652918` / job `136722618230`.

## 2. Implementation

- [x] 2.1 `scripts/stalled_job_watchdog.py`: scan `in_progress` runs; require a concluded sibling job; budget = max(floor 15, factor 1.25 × median job-name wall time from the workflow's recent completed runs), fallback 60 min without history; print `STALL` findings naming job, elapsed, budget derivation. (proven: live read-only replay `make check-stalled-jobs` rc=0 on the live board — no run past budget; the wedge fixture below reproduces the flagged shape)
- [x] 2.2 `--file`: resolve the run head's PR, post exactly one comment ending with the `<!-- stalled-job-watchdog: run <id> job <job-id> -->` marker, skip when the marker is already on that PR; no PR -> report only; never cancel. Exit contract 0/1/2/3. (proven: `python3 -m pytest tests/test_stalled_job_watchdog.py` rc=0 — 7 passed in `llgenie/test:latest`)
- [x] 2.3 `make check-stalled-jobs` in mk/bots.mk (+ `.PHONY`); wire the step into `.github/workflows/zero-job-pending.yml` (header Flow line updated). (proven: `make check-wiring` rc=0, `make check-workflows` rc=0, `make lint` rc=0)

## 3. Tests (`tests/test_stalled_job_watchdog.py`, `gh` stubbed on PATH)

- [x] 3.1 AC1: concluded sibling + `in_progress` job past budget -> exactly one finding naming the job and elapsed; `--file` posts exactly one comment on the PR. (proven: `python3 -m pytest tests/test_stalled_job_watchdog.py` rc=0)
- [x] 3.2 AC2: `in_progress` job within budget -> no finding, no comment. (proven: `python3 -m pytest tests/test_stalled_job_watchdog.py` rc=0)
- [x] 3.3 AC3: marker already on the PR -> replay posts no second comment. (proven: `python3 -m pytest tests/test_stalled_job_watchdog.py` rc=0)
- [x] 3.4 All-`in_progress` run (no concluded sibling) -> no finding; no-PR run named in report only; no-history fallback budget applied. (proven: `python3 -m pytest tests/test_stalled_job_watchdog.py` rc=0)

## 4. Gates

- [x] 4.1 The lane's focused battery exits 0 with the new tests: `python3 -m pytest tests/test_stalled_job_watchdog.py tests/test_check_zero_job_pending.py tests/test_ci_verdict.py tests/test_auto_merge.py tests/test_check_docs.py` in `llgenie/test:latest`. (proven: replayed at this head, rc=0)
- [x] 4.2 `make check-workflows` and `make openspec-validate NAME=stalled-job-watchdog-2992` exit 0. (proven: both replayed on this branch, rc=0)
