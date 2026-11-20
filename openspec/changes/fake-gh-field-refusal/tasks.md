# Tasks: fake-gh-field-refusal

Prerequisite (before any code): this branch MUST be rebased onto an `origin/main` that carries
`tests/fixtures/gh-json-fields.json` (lands via the PR closing #515).

- [x] Rebase onto `origin/main` carrying the fixture; `git cat-file -e HEAD:tests/fixtures/gh-json-fields.json` exits 0.
- [x] `tests/gh_fake.py`: `enforce(argv)` + `preamble(tests_dir)` per the spec (attribution mirrors `scripts/check_gh_json_fields.py`; refusal prints `Unknown JSON field: "<name>"` + exit 1).
- [x] `tests/test_gh_fake.py` green: refusal of the `authorAssociation` shape, valid-list pass-through, fixture identity (`pytest tests/test_gh_fake.py` rc=0).
- [x] Migrate heredoc'd fakes to the `preamble` guard line and function-shaped fakes to a direct `enforce` call across the 15 responder files (measured roster: test_code_review, test_issue_refiner, test_rebase_bot_sweep, test_arms, test_holds, test_pr_reconcile_guard, test_arm_pr (bash guard via `python3 gh_fake.py "$@"`), test_issue_implementer, test_auto_merge, test_check_pr_acceptance, test_pr_hygiene_commit_checkboxes, test_issue_cleaner, test_pr_body_write, test_queued_run_alarm, test_run_failure_reactor); each migrated file keeps its existing assertions green (`pytest <file>` rc=0 each).
- [x] `tests/test_auto_merge.py`: inline `--json` validation re-homed onto `gh_fake` without weakening the pinned behaviour.
- [x] One red pin per migrated family: the leg asks the `authorAssociation` shape, its own fake refuses (each red-pin test rc=0 asserting the refusal; `pytest` over all 15 responder files + `test_gh_fake.py` rc=0, 540 passed, 2026-11-20).
- [x] `make lint`, `make check-wiring`, `make check-workflows`, `make check-docs` rc=0.
- [x] agent-wiki entry + `docs/changes.d/` fragment; `make changes-index` then `make check-docs` rc=0.
- [x] `make -s openspec-validate NAME=fake-gh-field-refusal` rc=0.
- [x] Full battery `make test-unit` rc=0 at the committed head.

Ship (outside the checklist): push `feat/fake-gh-field-refusal-2975`, open the PR closing #2975
with the AC mirrors ticked on both bodies.
