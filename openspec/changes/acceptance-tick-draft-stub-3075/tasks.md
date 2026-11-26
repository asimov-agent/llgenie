# Tasks: acceptance-tick-draft-stub-3075

- [x] Add the shared draft-stub regex to `scripts/check_pr_acceptance.py` and refuse stub-carrying
      clauses in `_is_provable_tick`
- [x] Refuse stub-carrying proven clauses in `scripts/check_pr_hygiene.py` commit-checkboxes
- [x] Pin both refusals with cases in `tests/test_check_pr_acceptance.py` and
      `tests/test_pr_hygiene_commit_checkboxes.py` (the exact `#3035` residue clause shapes)
- [x] `python3 -m pytest tests/test_check_pr_acceptance.py tests/test_pr_hygiene_commit_checkboxes.py`
      rc=0 (92 passed), and `make openspec-validate NAME=acceptance-tick-draft-stub-3075` rc=0
- [x] agent-wiki entry + `docs/changes.d` fragment + `make changes-index` rc=0 (issue #3075 named,
      side issue #3076 linked)
