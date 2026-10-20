# Tasks

- [x] 1. `tests/fixtures/unit-suite.json` — the `groups` section with `fast`: the six hermetic files the loop's fast stage runs, with a reason, the issue (#403), the date and the files
- [x] 2. `scripts/unit_tests.py` — `--group NAME` on `list`/`argv`/`run`/`report`: `run --group fast` computes exactly the group's files; a group naming a file that is gone, excluded or repeated, or a group with no file or no reason/issue/date, is a finding; an unknown group is fatal (exit 2) before pytest starts
- [x] 3. Makefile: `test` runs `python scripts/unit_tests.py run --group fast` — the recipe names no test file at all
- [x] 4. `scripts/check_wiring.py` — `_aggregated` reads the `--group` argument from a recipe and asks the aggregator for that group's list, so `make test` is attributed only the group's files and `make test-unit` keeps the whole selection
- [x] 5. `tests/test_unit_suite.py` — the group contract: the real roster's group and recipe, the fault directions (gone/excluded/no-file/no-reason/unknown-group), and the wiring attribution of `make test` vs `make test-unit`
- [x] 6. `AGENTS.md` — states the rule: a subset a target runs is a named group in the roster, never a hand-list in a recipe
- [x] 7. `README.md` — documents the group, the `--group` command and `make test`'s seam; `agent-wiki/2026-10-20-unit-suite-fast-group.md` records the change, referencing issue #403
- [x] 8. Verified: `python3 scripts/unit_tests.py check` exit 0 (`76 of 91 selected; 15 excluded; 3 de-selected; 1 named group`); `list --group fast` prints the six files; `tests/test_unit_suite.py` (13) and `tests/test_wiring.py` + `tests/test_check_docs.py` (18) green in `llgenie/test:latest`; `make check-wiring` exit 0; `make openspec-validate NAME=unit-suite-fast-group` exit 0
