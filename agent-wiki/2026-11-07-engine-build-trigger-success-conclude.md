# 2026-11-07 — engine-build-pr-trigger concludes on a SUCCESS producer (#1994)

## The defect

`scripts/engine_build_trigger.py::_dispatch_and_wait` concluded the wait only on
`run.status == "completed"` or the `wait_min` deadline. A `push=true` engine-build producer that
**SUCCEEDED** but whose run object reads to the poll as a stale/mid-flight snapshot — `{status:
in_progress, conclusion: success}`, or the measured `{status: completed, conclusion: success,
completed_at: null}` — never flips to `completed`, so the trigger polled the green producer past its
wall-clock bound. Measured (#1994): trigger run `42352054921` sat `in_progress` 3h54m on producer run
`42352074711` which was `{status: completed, conclusion: success, completed_at: null}`. The `#1936`
cancelled/skipped-terminal fix (#1931 family) did not cover the green mirror.

## The change

- `_dispatch_and_wait` now treats a producer `conclusion` of `success` as **terminal**: it returns
  immediately with `conclusion: "success"` (no `cause`, no `expired`), so `check()`'s existing success
  branch prints `[will] OK engine=<e>: producer run <id> success` and returns 0. The terminal decision
  comes from the CONCLUSION, never the status field — the same rule `#1936` set for `cancelled`/`skipped`.

## Evidence

`tests/test_engine_build_trigger.py` 13 passed (12 prior + 1 new:
`test_success_producer_terminates_even_with_status_not_completed`); the new test drives
`{status: in_progress, conclusion: success}` with `--wait-min 0` and is proven to FAIL FAST
(deadline expiry) against the pre-fix code, then passes with the fix. `git diff` touches only the
script, its test, this openspec change and this note + its fragment. Implements #1994.
