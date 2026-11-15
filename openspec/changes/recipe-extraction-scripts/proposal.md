# Proposal: extract the five longest Makefile recipes into scripts/ entry points

## Why

Issue #2675: #800 criterion 5 — "the five longest recipes are each ≤ 3 lines and their logic
lives in a `scripts/*.py` entry point with unit tests" — is entirely unmet. Measured at
`origin/main@dcfb96b7df`: `help` (Makefile:744, 60 recipe lines), `ci-unit` (mk/ci.mk:27, 51),
`test-clean` (mk/tests.mk:15, 15), `build-server` (mk/engines.mk:9, 15), `test-published-engine`
(mk/engines.mk:362, 12). `ci-unit` is the gate every PR passes; its sequencing is a 51-line
shell program no unit test reads. `help` is 60 lines of hard-coded `@echo` — the drift-prone
doc #681 wants generated.

## What Changes

- Five new entry points in `scripts/`: `ci_unit.py`, `make_help.py`, `test_clean.py`,
  `build_server.py`, `published_engine.py`. Each owns its stage's sequencing and exit codes.
- The five Makefile targets become **≤ 3-line** recipes that call the entry points (make
  variables are passed as argv/flags; `$(MAKE)` invocations become explicit `make` calls the
  scripts run).
- Hermetic unit tests per entry point in `tests/` (stubbed subprocess seam / `--dry-run`, no
  docker, no `network` marker) so they run inside `ci-unit` itself.
- Byte-parity constraints: `make help` output byte-identical to the pre-change capture at the
  PR base; `ci-unit` sub-target sequence and order identical (pre/post invocation lists in
  the PR body); `make -qp` target inventory identical; no workflow file edits.
- `tests/test_make_pytest_seam.py` and the `scripts/unit_tests.py` deselect/roster seam stay
  green; `scripts/secret_scan.py` (mk/security.mk) is the in-tree precedent shape.

## Impact

- `Makefile` `help`, `mk/ci.mk` `ci-unit`, `mk/tests.mk` `test-clean`, `mk/engines.mk`
  `build-server` + `test-published-engine`: recipe bodies move to `scripts/`; targets stay
  declared in place (no inventory delta, no moves between files).
- `make help` byte-identical (59 lines at base `dcfb96b7df`, sha recorded in tasks).
- Gate coverage INCREASES: the five stage programs become importable/testable Python.
