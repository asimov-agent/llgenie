# Tasks — fix-auto-merge-cron-odd-minutes

- [ ] 1. Move the `recheck` sweep's cron in `.github/workflows/auto-merge.yml` off `:00`/`:30` onto odd
      minutes at the same 30-minute cadence, recording the measurement in the comment beside it.
- [ ] 2. Add `test_every_cron_minute_is_odd` to `tests/test_bot_pipeline_isolation.py`: every cron minute in
      every workflow is odd, scope derived from the workflow files.
- [ ] 3. Add `test_the_auto_merge_sweep_stays_scheduled` to the same file: `auto-merge.yml` keeps a
      `recheck` job, a schedule, odd minutes, and `make auto-merge-recheck`.
- [ ] 4. Prove both guards fail on the old cron (`*/30 * * * *`) and pass on the new one, with real
      `make test-unit` output.
- [ ] 5. Document the change in `README.md` and record it in `agent-wiki/`.
- [ ] 6. `make openspec-validate NAME=fix-auto-merge-cron-odd-minutes` exits 0 and `make loop` is green.
- [ ] 7. After merge, verify the workflow produced a `schedule` run (`runs?event=schedule` non-zero) — the
      only proof the trigger works.
