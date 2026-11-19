# Spec delta: ci-scope-classification

## ADDED Requirements

### Requirement: The Makefile split is a scope wildcard

Every path under `mk/` (the Makefile split that defines the CI stages — `mk/ci.mk`, `mk/tests.mk`, `mk/engines.mk`, `mk/bots.mk` and siblings) SHALL match a glob in `scripts/ci_scope.py::WILDCARDS`, so a diff touching only `mk/**` selects every class instead of failing the `ci-scope` step with "matches no class".

#### Scenario: a recipe-only mk edit classifies

- **WHEN** the diff of a pull request touches only `mk/bots.mk`
- **THEN** `scripts/ci_scope.py::classify` returns `unmatched == []` and every class in `CLASSES` is selected
- **AND** the CLI `classify` command exits 0

#### Scenario: the test file mirrors the wildcard

- **WHEN** `tests/test_ci_scope.py` is read
- **THEN** its wildcard-path parametrize list contains a `mk/` path
- **AND** `pytest tests/test_ci_scope.py` exits 0

#### Scenario: docs trigger semantics stay unchanged

- **WHEN** the docs-class trigger tests run (`test_the_docs_trigger_list_matches_the_docs_class_minus_its_wildcards`, `test_the_trigger_list_is_the_docs_class_and_nothing_else`)
- **THEN** `DOCS_TRIGGER_IGNORE == CLASSES["docs"]` still holds
- **AND** no wildcard matching a docs glob was introduced by this change
