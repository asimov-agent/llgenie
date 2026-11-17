# Tasks: queued-alarm-ghost-immunity

- [x] 1. Write the proposal + spec (issue #2600): the squat detector reads the zero-job retirement
      ledger; a read-only confirmed-concluded probe (24h queue-expiry window + orphaned + all jobs
      concluded) for non-ledger ghosts; live squat semantics unchanged.
- [x] 2. `scripts/queued_run_alarm.py`: import `zombie_retired_run_ids`, define `QUEUE_EXPIRY_MINUTES`;
      `squat_runs()` returns `(orphans, expired, retired, confirmed)` and classifies the ledger and
      confirmed-concluded ghosts; `render_squat` names the retired/confirmed buckets; `main` unpacks
      the 4-tuple and only lets a LIVE orphan/expired squat make the gate red.
- [x] 3. `scripts/package-layers.json`: declare the `queued_run_alarm -> check_zero_job_pending`
      cross-group edge with its reason (the shared retirement ledger).
- [x] 4. Tests (`tests/test_queued_run_alarm.py`): ledger-retired named-never-counted (no extra `run
      view`); confirmed-concluded ghost named-never-counted-never-cancelled; never filed; a live
      orphan with pending jobs still RED and still filed.
- [x] 5. docs fragment + agent-wiki note + CHANGES.md row, referencing issue #2600.
- [x] 6. Verify: `python3 -m pytest tests/test_queued_run_alarm.py` green (30 passed),
      `python3 scripts/check_package_layers.py check` OK. The OpenSpec CLI could not be executed in
      the agent container — no docker daemon and no node/npm — so `make openspec-validate` runs in
      CI's node/docker-bearing environment; this change is hand-crafted to the CLI's canonical
      shape (same situation the sibling change `ci-queued-squat-classify` recorded).
