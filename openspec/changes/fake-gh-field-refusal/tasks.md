# Tasks: fake-gh-field-refusal

Prerequisite (before any code): this branch MUST be rebased onto an `origin/main` that carries
`tests/fixtures/gh-json-fields.json` (lands via the PR closing #515).

- [ ] Rebase onto `origin/main` carrying the fixture; `git cat-file -e HEAD:tests/fixtures/gh-json-fields.json` exits 0.
- [ ] `tests/gh_fake.py`: `enforce(argv)` + `preamble(tests_dir)` per the spec (attribution mirrors `scripts/check_gh_json_fields.py`; refusal prints `Unknown JSON field: "<name>"` + exit 1).
- [ ] `tests/test_gh_fake.py` green: refusal of the `authorAssociation` shape, valid-list pass-through, fixture identity (`pytest tests/test_gh_fake.py` rc=0).
- [ ] Migrate heredoc'd fakes to the `preamble` guard line and function-shaped fakes to a direct `enforce` call across all 17 files listed in the proposal; each migrated file keeps its existing assertions green (`pytest <file>` rc=0 each).
- [ ] `tests/test_auto_merge.py`: inline `--json` validation re-homed onto `gh_fake` without weakening the pinned behaviour.
- [ ] One red pin per migrated family: the leg asks the `authorAssociation` shape, its own fake refuses (each red-pin test rc=0 asserting the refusal).
- [ ] `make lint`, `make check-wiring`, `make check-workflows`, `make check-docs` rc=0.
- [ ] agent-wiki entry + `docs/changes.d/` fragment; `make changes-index` then `make check-docs` rc=0.
- [ ] `make -s openspec-validate NAME=fake-gh-field-refusal` rc=0.
- [ ] Full battery `make test-unit` rc=0 at the committed head.

Ship (outside the checklist): push `feat/fake-gh-field-refusal-2975`, open the PR closing #2975
with the AC mirrors ticked on both bodies.
