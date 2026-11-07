# engine-build-trigger-success-conclude

## Why

`engine-build-pr-trigger`'s `trigger` job hangs even when the `engine-build` producer it waits on has
**SUCCEEDED**. `scripts/engine_build_trigger.py::_dispatch_and_wait` concludes the wait only on
`run.status == "completed"` or the `wait_min` deadline; a SUCCESS producer whose run object reads to
the poll as a stale/mid-flight snapshot — `{status: in_progress, conclusion: success}`, or the
`{status: completed, conclusion: success, completed_at: null}` variant measured below — never flips to
`completed`, so the trigger polls past its wall-clock bound and every consumer is blind for hours.
Measured (#1994): trigger run `42352054921` hung `in_progress` 3h54m on producer run `42352074711`
which was `{status: completed, conclusion: success, completed_at: null}`. `#1936` made the
cancelled/skipped producer terminal; this is the green mirror.

## What changes

`scripts/engine_build_trigger.py`'s await loop treats a producer `conclusion` of `success` as
**terminal** — the same rule `#1936` established for `cancelled`/`skipped`, by the same reasoning: a
run's `conclusion` is only ever populated once the run has finished, so `success` IS the final verdict
regardless of what the `status` field reports. `_dispatch_and_wait` returns immediately with
`conclusion: "success"`; `check()`'s existing `outcome["conclusion"] == "success"` branch prints
`[will] OK engine=<e>: producer run <id> success` and returns 0. A regression test drives the wait loop
with a producer reporting `{status: in_progress, conclusion: success}` and asserts the trigger
terminates with a success verdict (rc 0) instead of polling out `wait_min`.

## Out of scope

- The surrogate/cuda cell defect on #1982's branch (#2003, engine lane).
- The disk-floor class (#1915/#1933, in flight).
- #1982's rebase (the pr-merge-conflict sweep).
