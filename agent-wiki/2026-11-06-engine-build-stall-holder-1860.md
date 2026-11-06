# engine-build stall holder naming in engine_build_trigger (#1860)

Issue date: 2026-11-06. Implements the fix for #1860 opened by the engine-improver lane.

## The defect

A `push=true` engine-build dispatch serialises globally in `engine-build.yml`'s own
`concurrency.group: engine-build-push` (`cancel-in-progress: false`, issues #917/#621). When the
group holder is a run that is HUNG (a cell whose step stopped heartbeating — `updated_at` frozen,
later steps still `pending`), every later push dispatch sits `pending` with 0 jobs until that holder
concludes or is cancelled. Measured on #1696's valid channel `42201352115` @ `781f698a7e`: 3h+
pending/0-jobs behind holder `42191808660`'s hung vllm-rocm cell.

`scripts/engine_build_trigger.py` previously bailed at its own deadline with a bare
`concluded queued/None`, hiding that a re-dispatch is futile (it queues behind the same held gate).

## The change

- `_dispatch_and_wait` now detects an awaited `push=true` run left in `pending`/`queued`
  (0-jobs) and queries the in-progress push-group holder via the new `_push_group_holder`.
- The `FAIL engine=<e>` line names the holder and flags the run **STALLED**, stating that the
  holder must conclude or be owner-cancelled and that a re-dispatch queues behind the same gate.
- Two new unit tests in the fake-`gh` shape of `tests/test_engine_build_trigger.py`: the
  held-run case names the holder; the pending-with-no-holder case stays a plain failure.
- No dispatch/cancel behaviour changed — this is reporting-only. Owner never-kill / no-redispatch
  for the #1696 storm is untouched.

Evidence: `tests/test_engine_build_trigger.py` 9 passed; the engine-build sibling suites
23 passed; `git diff` touches only the script and its test.
