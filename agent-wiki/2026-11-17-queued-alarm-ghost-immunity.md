# Ghost-run squat immunity: the alarm learns the retirement ledger (issue #2600)

## What was verified against the spec

- **`queued_run_alarm.squat_runs()` now returns `(orphans, expired, retired, confirmed)`** and
  consults the ONE zero-job zombie-retirement ledger shared with the zero-job gate
  (`check_zero_job_pending.zombie_retired_run_ids`, issue #2600). A candidate whose id is already
  retired is reported as `retired (confirmed concluded earlier, #2600 mechanism; admin-only row, see
  #2606)` — named but never counted, never cancelled, never filed, and no `run view` round-trip
  spent by `squat_runs` (`test_a_ledger_retired_run_is_named_but_never_counted`).
- **A read-only concluded-jobs probe for non-ledger ghosts.** A run past the 24h queue-expiry window
  (`QUEUE_EXPIRY_MINUTES`) that is orphaned (no open PR, head branch deleted) AND whose instantiated
  jobs have ALL concluded is a confirmed-concluded ghost — named in its own bucket, never counted,
  never cancelled, never filed. This is what catches `43096752585` (one `completed` job, stuck row),
  which has jobs and so the zero-job gate can never retire it
  (`test_a_confirmed_concluded_ghost_is_named_but_never_counted`,
  `test_a_ledger_retired_or_confirmed_ghost_is_never_filed`).
- **Live squat semantics unchanged.** An orphaned queued run with a still-pending job stays a RED
  live-orphan finding and is filed exactly as today (`test_a_live_orphan_with_pending_jobs_is_still_red`).
- **`scripts/package-layers.json`** now states the `queued_run_alarm -> check_zero_job_pending`
  cross-group edge with its reason, and `python3 scripts/check_package_layers.py check` reports OK.

## Key decisions

- The 24h queue-expiry window is the same boundary GitHub uses for its own cleanup of runs pending
  > 24h with no jobs — a run past it that is orphaned AND fully concluded cannot progress further, so
  reading it as a ghost (never counted) is safe and read-only.
- Retired/confirmed-concluded ghosts are NAMED in the report so the alarm keeps its evidence, but
  only a LIVE orphan/expired squat makes the gate red (`has_squat = bool(orphans or expired)`).
- "Never cancel a run" stays true: the fix reads ledgers and job rows, it never cancels, never
  deletes, never files a retirement — filing NEW family stays the zero-job lane's job (#2600).

## Current status

- New tests: 4 in `tests/test_queued_run_alarm.py` (ledger-retired, confirmed-concluded, never-filed,
  live-orphan-still-red). Module green: `30 passed`.
- `make check-package-layers` OK (170 modules, 63 cross-group edges stated, 0 cycles).
- The OpenSpec CLI could not run in the agent container (no docker daemon, no node) — the change is
  hand-crafted to the canonical shape, as the sibling change `ci-queued-squat-classify` recorded;
  `make openspec-validate NAME=queued-alarm-ghost-immunity` runs in CI's node/docker environment.
