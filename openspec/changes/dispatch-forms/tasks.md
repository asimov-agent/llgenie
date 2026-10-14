# Tasks

- [x] 1. `scripts/check_dispatch_forms.py`: the name rule, the dispatch-form rule, the header rule, the
      README-table rule, and a `report` mode that generates the table.
- [x] 2. Apply it to every dispatchable workflow: `engine-bump-rebase`, `engine-bump`, `fix-bot`,
      `issue-bot`, `publish-agent-image`, `queued-alarm`, `registry-sync`.
- [x] 3. `engine-bump-rebase` gets a `dry` input that reaches the code, via a new
      `make engine-bump-rebase` target (and the step stops calling the script inline).
- [x] 4. `queued-alarm.yml` calls `make queued-alarm` (closes #270).
- [x] 5. `tests/test_dispatch_forms.py` (22 tests) wired into `test-unit`; the guard runs over this
      repository and requires every bot workflow to be dispatchable, named and documented.
- [x] 6. The README's dispatch table, generated from the workflows and verified by the guard.
- [x] 7. Verify: `pytest tests/test_dispatch_forms.py`, `make check-dispatch-forms`,
      `make check-wiring`, `make lint`.
