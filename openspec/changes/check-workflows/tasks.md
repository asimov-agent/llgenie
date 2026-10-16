# Tasks

- [x] 1. Write the proposal + spec for the workflow gate (issue #330).
- [x] 2. `.github/workflows/engine-bump-rebase.yml`: the `run:`-block comment no longer writes expression
      syntax, and it says why it must not. `actionlint` is clean on the file and both `run:` blocks still
      pass `bash -n`.
- [x] 3. `scripts/check_workflows.py` (`check` / `report`), stdlib only so `ci-unit` runs it on the host on
      Linux and macOS alike: every YAML file's `${{ ... }}` must parse, every YAML file must end with a
      newline, and every `.github/workflows/*.yml` must declare a top-level `name:`.
- [x] 4. `make check-workflows` / `make workflows-report`, the first wired into `ci-unit` after
      `check-pr-hygiene`, both declared in `.PHONY`.
- [x] 5. `tests/test_workflows_valid.py` (wired into `test-unit`, which `ci.yml` runs): the pre-fix line is
      caught, the expression forms this repo uses are not false positives, every YAML file parses strictly
      with no duplicate keys, and the exit-code contract. 11 cases.
- [x] 6. `AGENTS.md`: the durable section — a `#` inside `run:` is script text, `yaml.safe_load` does not
      save you, a 0-job run named after the path is a startup failure, and `make check-workflows` is the gate.
- [x] 7. README line for both targets plus the rule, and the `agent-wiki/` work record naming `#330` and
      `#329`.
- [x] 8. Verify: `tests/test_workflows_valid.py` 11 passed and 88 passed across the seven touched suites in
      `llgenie/test:latest`; `make check-workflows` reports exactly one violation on `origin/main`'s file and
      0 on this tree; `actionlint` clean; `make lint`, `make check-docs`, `make check-wiring`,
      `make check-pr-hygiene`, `make check-dispatch-forms`, `make check-secret-output`,
      `make openspec-validate NAME=check-workflows`.
