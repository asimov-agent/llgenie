# engine-build-push-queue-fifo — proposal

Issue: [#2301](https://github.com/asimov-agent/llgenie/issues/2301)

## Why

`.github/workflows/engine-build.yml`'s shared push `concurrency:` group declared `cancel-in-progress:
false` but no `queue:` key, so GitHub's default `queue: single` applied: a newer pending push=true
dispatch CANCELS AND REPLACES the older pending producer. `cancel-in-progress: false` protects only the
RUNNING run, never a pending one, so every newer engine-build dispatch killed the queued producer of
the six open engine-bump PRs, leaving each `engine-build-pr-trigger` red with `producer cancelled —
nothing to wait for` (#2294). Measured supersede chain `42522061057 -> 42524063205`; control run
`42524592612` (push=false, disjoint `build-llama.cpp-cpu` group) concluded `success`, proving the run
layer is healthy and only the shared push group's supersede is the canceller.

## What Changes

- **`.github/workflows/engine-build.yml`** — the shared `concurrency:` block gains `queue: max` beside
  the existing `cancel-in-progress: false`, so the push group holds up to 100 pending runs FIFO and each
  reaches a real conclusion instead of being replaced. `queue: max` + `cancel-in-progress: false` is the
  validated pairing (the alternative, `queue: max` + `cancel-in-progress: true`, is invalid). The group
  stays global so the `:<arch>` tag race (#917) stays closed.
- **`tests/test_ci_concurrency.py`** — `test_engine_build_pending_push_queue_runs_fifo` asserts the
  PARSED `concurrency.queue == "max"` (never the file text, which a comment alone could satisfy).

Only the workflow's concurrency block and its parse test change; the build producer is untouched.

## Change-first

Issue #2301 is the surviving tracker, delivered as PR #2304. `make check-workflows` and `make
check-wiring` are green with quoted exit codes; the new parsed-map test is the pin, its negative control
measured locally (reverting the `queue:` key reds the test). Base: `origin/main@aef9ee7b`. Branch:
`ci/2301-engine-build-queue-max`.
