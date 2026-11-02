# architecture-census

## MODIFIED Requirements

### Requirement: every named §Scripts module resolves to a tracked file at the measured sha

The census gate MUST check referent membership, not just directory totals: every `scripts/*.py` or
`scripts/*.sh` module name that appears inside the §Scripts table in `docs/ARCHITECTURE.md` (and the
parallel BOTS.md sentence) MUST resolve to a tracked file at the measured sha. The check is a subset
check (named modules ⊆ tree at the sha), never equality, so a legitimate future addition does not red
it. A named module that does not exist at the measured sha MUST fail the gate, naming that module.

WHEN the census gate runs and a `scripts/*.py` or `scripts/*.sh` name in the §Scripts table (or the
parallel BOTS.md sentence) is absent from `git ls-tree -r --name-only <sha> -- scripts/`
THEN the gate exits non-zero and names that module.

#### Scenario: a removed §Scripts module reddens the gate with its name

- **Given** a tree whose §Scripts table names `scripts/engine_matrix_pushed.py` but whose measured
  sha does not contain that file
- **When** the census gate runs at that sha
- **Then** it exits non-zero and its output names `engine_matrix_pushed.py`
- **Test:** `tests/test_architecture_census.py::test_a_removed_scripts_module_reddens_naming_it`

#### Scenario: a clean tree with all named modules present passes

- **Given** a tree whose §Scripts table names only modules that exist at the measured sha
- **When** the census gate runs
- **Then** it exits 0 (the referent check adds no finding to the count checks)
- **Test:** `tests/test_architecture_census.py::test_all_named_scripts_modules_resolve_passes`

#### Scenario: a future module addition does not red the referent check

- **Given** a tree whose §Scripts table names a subset of the modules present at the measured sha
- **When** the census gate runs
- **Then** it exits 0, because the check is subset (named ⊆ tree), not equality
- **Test:** `tests/test_architecture_census.py::test_a_table_that_names_a_subset_passes`
