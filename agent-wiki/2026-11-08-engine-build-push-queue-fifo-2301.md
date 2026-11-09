# 2026-11-08 — engine-build push runs queue FIFO instead of cancelling (issue #2301, #2294)

## The defect

`.github/workflows/engine-build.yml`'s shared `concurrency:` group guarded pushtime runs with
`group: engine-build-…push…` and `cancel-in-progress: false` but declared no `queue:` key. GitHub's
default for a concurrency group is `queue: single`: a NEWER dispatch CANCELS AND REPLACES any PENDING
run already in the group. `cancel-in-progress: false` protects only the RUNNING holder, never a pending
producer, so every newer push=true engine-build dispatch killed the queued producer of the six open
engine-bump PRs — each `engine-build-pr-trigger` red with `producer cancelled — nothing to wait for`
(#2294). Measured supersede chain `42522061057 -> 42524063205`; control run `42524592612` (`push=false`,
disjoint `build-llama.cpp-cpu` group) concluded `success`, proving only the shared push group's
supersede is the canceller.

## The change

- `.github/workflows/engine-build.yml` — the shared push `concurrency:` block gained `queue: max`
  beside the existing `cancel-in-progress: false`, so the group holds up to 100 pending runs FIFO and
  each reaches a terminal verdict instead of being replaced. `queue: max` + `cancel-in-progress:
  false` is the validated pairing; the group stays global so the `:<arch>` tag race (#917) stays
  closed.
- `tests/test_ci_concurrency.py::test_engine_build_pending_push_queue_runs_fifo` asserts the PARSED
  `concurrency.queue == "max"` (never the file text, which a comment alone could satisfy).

## Evidence

The new parsed-map test plus the existing `test_engine_build_serialises_publishing_runs_but_not_a_narrow_dispatch`
pass in the container; a local negative control (reverting the `queue:` key) reds the new test. The
workflow file change and the test are the whole diff (plus this change triplet). Implements #2301 via
PR #2304.
