# engine-build-stall-holder — proposal

Issue: [#1860](https://github.com/asimov-agent/llgenie/issues/1860)

## Why

A `push=true` engine-build dispatch serialises globally on `concurrency.group:
engine-build-push` (`cancel-in-progress: false`, issues #917/#621). When the group's holder is a
hung run (a cell whose step stopped heartbeating — `updated_at` frozen, later steps `pending`),
every later push dispatch sits `pending` with 0 jobs until the holder concludes or is
owner-cancelled. Measured on #1696's valid channel `42201352115` @ `781f698a7e` (3h+ pending/0-jobs
behind holder `42191808660`'s hung vllm-rocm cell). `scripts/engine_build_trigger.py` bailed at its
deadline with a bare `concluded queued/None`, hiding that a re-dispatch is futile.

## What Changes

- **`scripts/engine_build_trigger.py`** — `_dispatch_and_wait` detects an awaited `push=true` run
  left `pending`/`queued` (0-jobs, no heartbeat), queries the in-progress push-group holder via the
  new `_push_group_holder`, and the `FAIL engine=<e>` line names the holder, flags the run
  **STALLED**, and says a re-dispatch queues behind the same gate.
- **`tests/test_engine_build_trigger.py`** — two new tests in the fake-`gh` shape: held-run names
  the holder; pending-with-no-holder stays a plain failure.
- Reporting-only; no dispatch/cancel behaviour changed (owner never-kill / no-redispatch for the
  #1696 storm untouched).
