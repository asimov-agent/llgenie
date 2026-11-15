## ADDED Requirements

### Requirement: The five longest recipes are thin wrappers over scripts/ entry points

The targets `help`, `ci-unit`, `test-clean`, `build-server` and `test-published-engine`
SHALL each carry a recipe of at most 3 lines that calls a `scripts/` Python entry point
(`make_help.py`, `ci_unit.py`, `test_clean.py`, `build_server.py`,
`published_engine.py`). The sequencing logic and exit-code handling SHALL live in the
entry points, not in the recipes. The target declarations, names, prerequisites and `##`
help lines SHALL stay in their current makefiles (no moves, no inventory delta).

#### Scenario: recipe length at head

- **WHEN** the recipe blocks of the five targets are measured at head
- **THEN** each carries at most 3 recipe lines and the first names its `scripts/*.py` entry point

#### Scenario: target inventory is unchanged

- **WHEN** `make -qp` sorted-unique inventories are diffed base vs head
- **THEN** the inventories are byte-equal and `make check-wiring` is green

### Requirement: The extracted entry points are hermetically unit-tested

Each entry point SHALL have a test module in `tests/` that runs its sequencing against a
stubbed subprocess seam (or `--dry-run`), with no docker, no network and no `network`
marker, so the tests run inside `ci-unit` itself.

#### Scenario: the five stage tests run in the hermetic suite

- **WHEN** `make ci-unit` runs at head
- **THEN** `tests/test_ci_unit_stage.py`, `tests/test_make_help_stage.py`,
  `tests/test_test_clean_stage.py`, `tests/test_build_server_stage.py` and
  `tests/test_published_engine_stage.py` all pass without docker or network

### Requirement: help output is byte-identical to the pre-change capture

`scripts/make_help.py` SHALL emit the help text captured from `make help` at the PR base
(commit `dcfb96b7df`, 59 lines, sha256 `1eb759c19f760317…`), and the capture SHALL be
committed as `tests/fixtures/make-help-base.txt` so the parity is re-checkable forever.

#### Scenario: cmp base capture vs new output

- **WHEN** `make help` at head and `cmp` against `tests/fixtures/make-help-base.txt` run
- **THEN** cmp exits 0 (byte-identical, 59 lines)

### Requirement: ci-unit semantics are unchanged

`scripts/ci_unit.py` SHALL hold the 51 sub-target invocations as an ordered, ordered-exact
`MAKE_SEQUENCE` of `make <target> …` command strings (including the
`skills-validate REGISTRY=… UNSUPPORTED=…` override step), run them sequentially with
fail-fast, and expose `sequence_targets()` for the consumers. `scripts/issue_bot_gates.py`
and `scripts/check_wiring.py` SHALL read each entry point's embedded `make <target>`
sequence through one discovery seam (the #393 aggregator-seam precedent extended to
entry-point scripts), so the gate classification (#475), the CI target closure and every
`##` CI claim survive the extraction unchanged.

#### Scenario: pre/post invocation lists are identical

- **WHEN** the sub-target invocation list recorded from the base recipe and the list from
  `scripts/ci_unit.py` at head are diffed
- **THEN** they are byte-equal (51 entries, same order)

#### Scenario: a new unclassified gate in the sequence still reds the issue-bot gate

- **WHEN** an entry naming a gate classified in neither `FAST_GATES` nor `DEFERRED` is added
  to `MAKE_SEQUENCE`
- **THEN** `make issue-bot-gates` fails with the #475 finding

### Requirement: build-server and test-published-engine orchestration is preserved

`scripts/build_server.py` SHALL reproduce the observable flow of the old recipe (detect
banner, `detect_server` call, tree/backend decision, tee'd build log, binary-exists check,
stamp write, log cleanup, final banner). `scripts/published_engine.py` SHALL preserve the
usage guard text, `engine_image.py pull-published` call, `make test-engine-image` delegation,
the `engine_test` runner invocation of `tests/test_published_engine_binary.py` via the
make-expanded `PE_TEST` environment seam, the `CI_HOME` create/clean pair, and the final
published banner. No workflow file may be edited.

#### Scenario: no workflow edits

- **WHEN** the PR diff is inspected
- **THEN** no file under `.github/workflows/` changed and `make check-workflows` is green
