# check-workflows

## ADDED Requirements

### Requirement: A `${{ ... }}` GitHub cannot parse is a violation

`make check-workflows` SHALL fail when any YAML file in the repository contains a `${{ ... }}` whose
expression does not parse, naming the file, the line and the offending token. The check SHALL read the raw
text of the file — a `#` line inside a `run:` block scalar is script content, so an expression written
there SHALL be validated exactly as one in a `value:`. GitHub refuses the WHOLE file for such an
expression, which is what makes a workflow produce a 0-job, log-less, `conclusion=failure` run named after
its path. The expression SHALL be parsed by a real parser over GitHub's grammar (`||`, `&&`, comparisons,
`+ - * / %`, unary `! -`, property access, `.*`, `[...]`, function calls, numbers, single-quoted strings,
`true`/`false`/`null`), so an expression this repository already uses SHALL NOT be a false positive.

#### Scenario: an unparseable expression in a run block

- **GIVEN** a workflow whose `run: |` block contains `${{ ... }}`
- **WHEN** `make check-workflows` runs
- **THEN** it SHALL exit non-zero and name that expression as unparseable
- **Test:** `tests/test_workflows_valid.py::test_a_malformed_expression_is_a_violation`

#### Scenario: the exact line that shipped on main

- **GIVEN** the pre-fix comment `# folded into one \`${{ ... }}\` so the mode this run took is readable in the log.`
- **WHEN** the gate reads it
- **THEN** it SHALL report the unparseable expression and name the unexpected token
- **Test:** `tests/test_workflows_valid.py::test_the_pre_fix_comment_is_a_violation`

#### Scenario: the expressions this repository already uses

- **WHEN** every expression form used in this repository's workflows is parsed
- **THEN** none of them SHALL be reported
- **Test:** `tests/test_workflows_valid.py::test_common_github_expression_shapes_all_parse`

### Requirement: Every YAML file is in scope

The gate SHALL read every YAML file in the repository — not only `.github/workflows/*.yml` — because the
same expression rule applies wherever GitHub reads an expression and the user asked for all of them to be
validated each run. In a git checkout the file list SHALL come from git's index; a tree that is not its own
checkout SHALL be walked, so a fixture can never be read through some enclosing repository's index and
silently report nothing.

#### Scenario: a non-workflow YAML file

- **GIVEN** a top-level `a.yml` carrying an unparseable expression
- **WHEN** the gate lists the files it reads
- **THEN** `a.yml` SHALL be in the list and its expression SHALL be reported
- **Test:** `tests/test_workflows_valid.py::test_the_gate_reads_every_yaml_file_not_only_the_workflows`

#### Scenario: every YAML file parses strictly

- **GIVEN** this repository's YAML files
- **WHEN** each is parsed with a loader that refuses a duplicate key
- **THEN** none SHALL fail, and the file list SHALL NOT be empty
- **Test:** `tests/test_workflows_valid.py::test_every_yaml_file_in_this_repository_parses_with_no_duplicate_keys`

### Requirement: The repository's lint specs hold for the YAML files

The gate SHALL fail on a YAML file that does not end with a newline (the repository's linefeed lint spec),
and on a `.github/workflows/*.yml` with no top-level `name:` — a missing name is what makes a run present
itself as a file path, which is indistinguishable from a startup failure in `gh run list`.

#### Scenario: no trailing newline

- **GIVEN** a YAML file whose last byte is not a newline
- **WHEN** the gate reads it
- **THEN** it SHALL report the missing newline
- **Test:** `tests/test_workflows_valid.py::test_a_missing_trailing_newline_is_a_violation`

#### Scenario: no workflow name

- **GIVEN** a workflow with no top-level `name:`
- **WHEN** the gate reads it
- **THEN** it SHALL report the missing name
- **Test:** `tests/test_workflows_valid.py::test_a_missing_workflow_name_is_a_violation`

### Requirement: The gate runs on every CI run and this repository passes it

`make check-workflows` SHALL run inside the `ci-unit` job (which `ci.yml` runs on Linux and macOS), and the
gate's tests SHALL run in `make test-unit`. Every YAML file in this repository SHALL pass the gate.

#### Scenario: the exit code is what CI gates on

- **WHEN** the gate finds a violation in a fixture tree
- **THEN** `main(["check"])` SHALL return non-zero, and 0 on this repository's tree
- **Test:** `tests/test_workflows_valid.py::test_check_exits_non_zero_on_a_violation_and_zero_on_this_repo`

#### Scenario: this repository passes its own gate

- **WHEN** the gate runs over this repository
- **THEN** it SHALL report no violation
- **Test:** `tests/test_workflows_valid.py::test_this_repository_passes_its_own_gate`

#### Scenario: a clean expression is accepted

- **WHEN** a workflow's only expression is `${{ github.repository }}`
- **THEN** nothing SHALL be reported
- **Test:** `tests/test_workflows_valid.py::test_a_valid_expression_is_accepted`
