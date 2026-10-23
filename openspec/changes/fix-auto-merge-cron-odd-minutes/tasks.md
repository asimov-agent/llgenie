# Tasks — fix-auto-merge-cron-odd-minutes

- [x] 1. Move the `recheck` sweep's cron in `.github/workflows/auto-merge.yml` off `:00`/`:30` onto odd
      minutes at the same 30-minute cadence, recording the measurement in the comment beside it.
- [x] 2. Add `test_every_cron_minute_is_odd` to `tests/test_bot_pipeline_isolation.py`: every cron minute in
      every workflow is odd, scope derived from the workflow files.
- [x] 3. Add `test_the_auto_merge_sweep_stays_scheduled` to the same file: `auto-merge.yml` keeps a
      `recheck` job, a schedule, odd minutes, and `make auto-merge-recheck`.
- [x] 4. Prove both guards fail on the old cron (`*/30 * * * *`) and pass on the new one, with real
      `pytest tests/test_bot_pipeline_isolation.py` output (6 passed / 2 failed with `*/30` restored).
- [x] 5. Document the change in `README.md` and record it in `agent-wiki/`.
- [x] 6. `make check-workflows`, `make check-docs` and `make check-wiring` green.
- [x] 7. `make openspec-validate NAME=fix-auto-merge-cron-odd-minutes` exits 0, and both new guards are green
      under the unit gate (`make test-unit` runs `tests/test_bot_pipeline_isolation.py`).

The post-merge check — a `schedule` fires only from the default branch, so the proof the trigger works is a
non-zero `gh api repos/asimov-agent/llgenie/actions/workflows/auto-merge.yml/runs?event=schedule` — is not a task
here: it cannot be ticked before the merge. It is #560's last `Done when` box and the agent-wiki entry's
"Not verified here" section.
