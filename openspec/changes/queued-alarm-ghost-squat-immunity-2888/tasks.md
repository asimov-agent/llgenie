# Tasks — queued-alarm-ghost-squat-immunity-2888

- [x] 1. `squat_runs()` reads the retirement ledger once per scan (`check_zero_job_pending.zombie_retired_run_ids`): ledger ids are named `retired`, never counted, and cost no jobs/PR round-trip.
- [x] 2. Non-ledger orphan candidates past GitHub's 24h queued window read their job rows once: instantiated AND all-concluded → CONFIRMED-CONCLUDED GHOST (named, never counted, never cancelled, never filed); no-jobs or not-all-concluded candidates stay live squat exactly as today.
- [x] 3. `render_squat` + `main()` name the `retired` and `ghost` buckets; the exit code and the squat-issue filing react only to LIVE squat; report line keeps ghosts visible. Add the `--dry` switch (nothing filed, same exit codes) and wire `DRY=1` through the make target.
- [x] 4. `tests/test_queued_run_alarm.py`: add the four spec-named tests (ledger immunity, concluded ghost, live orphan still red+filed, mixed naming); all pre-existing squat tests keep passing.
- [x] 5. `scripts/package-layers.json`: declare `queued_run_alarm -> check_zero_job_pending` edge with a reason; `make check-package-layers` rc=0.
- [x] 6. Docs: `docs/BOTS.md` queued-alarm paragraph states the ghost/retired buckets; `docs/changes.d/` fragment + `agent-wiki/` note; `make -s changes-index` + `make check-docs` rc=0.
- [x] 7. Live replay: `make -s queued-alarm` against the live repo names the six measured ghosts (5 retired + 1 concluded) and exits 0 with no filing.
- [x] 8. Verification (tick when each measurement is on disk): `pytest tests/test_queued_run_alarm.py tests/test_check_zero_job_pending.py` rc=0; `make openspec-validate NAME=queued-alarm-ghost-squat-immunity-2888` rc=0; `make test-unit` rc=0.
