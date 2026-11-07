# engine-build-trigger-cancelled

## Why

`engine-build-pr-trigger`'s `trigger` job hangs forever when the `engine-build` producer it waits on
is **cancelled**. `scripts/engine_build_trigger.py::_dispatch_and_wait` concludes the wait only on
`run.status == "completed"` or the `wait_min` deadline; a run cancelled mid-wait (a newer push triggers
`engine-build.yml`'s concurrency cancel) can report `conclusion: "cancelled"` while its `status` stays
`in_progress`/`queued`, so the trigger polls a corpse. Measured (#1931): trigger run `42326516316` sat
`in_progress` 3.5h on producer run `42326545643` which was CANCELLED 12 s after the trigger started —
freezing #1696's CI, holding the rebase lane's "a run is in progress" guard on a dead matrix, and
leaving `ci-verdict` red forever.

## What changes

`scripts/engine_build_trigger.py`'s await loop treats a producer conclusion of `cancelled` or
`skipped` as **terminal**: it stops polling immediately and the FAIL line names the cause (`producer
<conclusion> — nothing to wait for`) instead of waiting the producer out. The wall-clock bound is made
explicit: when `wait_min` expires and the run has never concluded, the FAIL line names the producer run
id and its last known status (`wait bound (<n> min) expired — producer run <id> never concluded, last
status <status>`), instead of the bare `concluded <status>/<conclusion>` that read like a verdict that
never happened. A registration test drives the wait loop with a cancelled producer and asserts the
trigger terminates.

## Out of scope

- Why the producer was cancelled (concurrency `cancel-in-progress` on a newer push) — expected, not a
  defect.
- The `engine-build` producer matrix itself — owned by #1915.
- The `ci-verdict` red on the dead run — resolves once the trigger terminates (out of scope here).
