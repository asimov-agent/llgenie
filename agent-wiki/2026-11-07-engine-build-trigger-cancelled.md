# 2026-11-07 — engine-build-pr-trigger terminates on a cancelled/skipped producer (#1931)

## The defect

`scripts/engine_build_trigger.py::_dispatch_and_wait` concluded the wait only on
`run.status == "completed"` or the `wait_min` deadline. A `push=true` engine-build producer cancelled
mid-wait (concurrency `cancel-in-progress` when a newer push hits `engine-build.yml`) can report
`conclusion: "cancelled"` while its `status` stays `in_progress` — so the trigger polled a corpse.
Measured (#1931): trigger run `42326516316` sat `in_progress` 3.5h on producer run `42326545643`
(CANCELLED 01:54:54Z, 12 s after the trigger started on #1696, head `26067a1f`). The dead run reads
`in_progress` to every consumer, reds `ci-verdict`, and held the rebase lane's "a run is in progress"
guard against a legitimate rebase.

## The change

- `_dispatch_and_wait` now treats a producer `conclusion` of `cancelled` or `skipped` as **terminal**:
  it returns immediately with a named `cause` (`producer cancelled — nothing to wait for` /
  `producer skipped — nothing to wait for`) instead of waiting the run out.
- The `wait_min` wall-clock bound is explicit: expiry fails naming the run id and its last known status
  (`wait bound (<n> min) expired — producer run <id> never concluded, last status <status>`), never the
  bare `concluded <status>/<conclusion>`. The #1860 STALLED-behind-holder naming now rides on that
  expiry line (it only ever fired on the deadline path).
- `check()` maps `cause` and `expired` into named FAIL lines.

## Evidence

`tests/test_engine_build_trigger.py` 12 passed (9 prior + 3 new: cancelled-terminates,
skipped-terminates, expiry-names-run-and-status); the two #1860 stall tests were updated to the
explicit expiry message shape (`git diff` touches only the script, its test, the openspec change and
this note + its fragment). Implements #1931.
