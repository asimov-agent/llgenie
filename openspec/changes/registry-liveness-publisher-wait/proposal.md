# registry-liveness-publisher-wait — proposal

Issue: [#2592](https://github.com/asimov-agent/llgenie/issues/2592)

## Why

`registry-liveness` triggers on every push to `main` and hard-fails (rc=1) when a committed engine
pin's tag resolves `manifest unknown` in GHCR. But on a push, the pipeline that *publishes* that very
tag — the `ci.yml` run on the same commit — is still in flight. Measured on `main` tip
`be92a32695ebf46c9b15386295c73be1331091fd`: run #457 (id 43289460942, head `be92a32695`) failed at
19:23:12Z with `[launchers] NOT PUBLISHED mlx: llgenie/mlx:93e6d4a6-e5ab3798-cpu resolves no manifest`
while CI run #5565 for the same head was still `in_progress`; that tag is published now. The same race
redded #454/#455 at head `85be1b6a87`. Liveness is the fleet's watchdog and now cries red on every
engine retag merge even though nothing is actually missing; each red is indistinguishable from a
genuine unpublished cell, and the standing rule "registry-liveness must not fail" is violated on every
retag.

The companion failure is the sweep: a run that raced the publisher then DISPATCHES an engine-build
sweep for the same SHA — reproducing the very failure it redded on. Sweeps #682/#684 (head
`85be1b6a87`, workflow_dispatch) failed `vllm-rocm ... Permission denied` because the fix landed only
in `b32594c8c4`; #456 (post-#2582) is green. Dispatching a sweep whose publisher already failed files
a second red run guaranteed to fail.

## What Changes

- **`.github/workflows/registry-liveness.yml`** — on a push-triggered run, a NEW step BEFORE the fleet
  gate waits (bounded) for the `ci.yml` run at the same head SHA to conclude; that run is the
  publisher for the pins in this tree. Only after it concludes does the manifest check decide
  (#2259/`#2190` contract unchanged for the successful-publisher and scheduled cases). When the
  publisher run concluded **failure**, the run does NOT dispatch an engine-build sweep — the tracking
  issue names the failed publisher run instead of dispatching a guaranteed-failing sweep. The fleet
  gate's `exit "$rc"` hard-fail, the issue-filer, and the `[select]` dispatch machinery are kept
  verbatim; the wait is added before, and the dispatch suppression is a guarded early-exit from the
  dispatch step.
- **tests** — new wiring assertions in `tests/test_check_engine_pins_published.py` lock the wait gate
  before the fleet check, the failure-suppressed dispatch, and the still-running (non-hard-fail) case.
- **no change** to `scripts/check_engine_launchers.py` — the wait gate is entirely workflow-side, as
  the issue specifies ("the wait gate is workflow-side").

## Impact

- **Good:** a push-triggered liveness run no longer races its own publisher. Red liveness again means
  "there is a real gap", and a sweep is never dispatched for a SHA whose own publisher failed.
- **Good:** scheduled runs are unchanged — they never race a same-head publisher, so they keep today's
  file-issue + dispatch + hard-fail contract.
- **Trade-off / risk:** a bounded wait that expires while the same-head publisher is STILL running must
  not hard-fail (that would reintroduce the race-red) and must not dispatch; the run records "wait
  exhausted, publisher still in flight" and defers the verdict to the next scheduled run (which, not
  racing, settles it definitively). This is the safe direction spelled out by the issue.

## Not covered

None in this change. See the separate change's tasks/spec for the full fleet liveness contract.
