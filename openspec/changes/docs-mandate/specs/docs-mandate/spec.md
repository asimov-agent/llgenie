# docs-mandate

## ADDED Requirements

### Requirement: A user-facing make target is documented, or recorded as an exception

`make check-docs` SHALL fail when a make target with a `##` help line is not mentioned in
`README.md`, naming the exact target, unless it is recorded in
`tests/fixtures/docs-exceptions.json` with a reason and a date. An exception the README now
documents SHALL itself fail, so the file cannot rot. Matching SHALL be whole-token: a README
mention of `docs-report` does not document `docs`.

#### Scenario: an undocumented target is loud

- **GIVEN** a make target with a `##` help line that the README never mentions
- **WHEN** `make check-docs` runs
- **THEN** it SHALL exit non-zero and name that target

#### Scenario: documenting it completes the fix

- **WHEN** the README mentions that target
- **THEN** `make check-docs` SHALL pass

#### Scenario: a stale exception fails

- **GIVEN** a recorded exception whose target the README now documents
- **THEN** `make check-docs` SHALL fail until the entry is removed

### Requirement: A work record names the issue or PR it implements

Every `agent-wiki/YYYY-MM-DD-<name>.md` record SHALL reference at least one issue or PR; a record
with none SHALL fail `make check-docs`, and `make docs-report` SHALL list each record's
references.

#### Scenario: an unreferenced record fails

- **GIVEN** a work record with no issue/PR reference
- **THEN** `make check-docs` SHALL fail until one is added

### Requirement: The gate is part of CI

`make ci-unit` SHALL run `make check-docs`, and the gate's own tests SHALL run in `make test-unit`.

#### Scenario: the chain includes the gate

- **WHEN** the `ci-unit` recipe and the unit-test list are read
- **THEN** they SHALL name `check-docs` and `tests/test_check_docs.py` respectively
