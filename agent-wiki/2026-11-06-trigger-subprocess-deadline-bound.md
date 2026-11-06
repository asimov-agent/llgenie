# 2026-11-06 — bound `engine-build-pr-trigger` subprocesses (issue #1838)

The trigger's dispatch/poll loop must give up when a repinned engine never publishes, not hang
past its own deadline.

**Measured defect:** `scripts/engine_build_trigger.py`'s `_sh`/`_gh` called `subprocess.run` with no
`timeout=`. A stalled `gh api` (a slow registry/API response) blocked the poll loop, so the
`time.time() > deadline` check (from `DEFAULT_MAX_WAIT`) was never reached. Live: trigger run
`42180155072`'s `make engine-build-pr-trigger` step sat `in_progress` ~69 min past its 60-min
`DEFAULT_MAX_WAIT` at head `7967bb3f` — the job-level `timeout-minutes: 250` was the effective bound,
a multi-hour invisible hang for any PR touching an engine.

**Fix:** every subprocess `_sh` runs (the `gh api` polls and the `gh workflow run` dispatch) is now
capped at `SUBPROCESS_TIMEOUT = 30s`; a `TimeoutExpired` yields `""` (or, for the dispatch, falls
through to the discovery loop) so the poll loop's own deadline remains the authoritative bound and
fails with the existing clear "[will] FAIL … concluded status/conclusion" message instead of hanging.

**Out of scope:** the abandoned `engine-pins` job does not exist on `main` (it is part of PR #1696's
own diff, already bounded at `WAIT=290` + `timeout-minutes: 300`) and the root never-publishes cause
is #1836 (default vllm = CPU) / #1832 (CUDA build).
