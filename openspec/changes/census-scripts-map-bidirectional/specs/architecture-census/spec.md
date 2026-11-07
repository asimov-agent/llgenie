# architecture-census

## MODIFIED Requirements

### Requirement: every tracked scripts module has a row in the §Scripts section

The census gate MUST check the reverse direction too — `tree ⊆ named-in-doc` — not just the existing
`named-in-doc ⊆ tree`. Every tracked `scripts/*.py` or `scripts/*.sh` basename at the measured sha
MUST be named somewhere in the §Scripts section of `docs/ARCHITECTURE.md`: in a group table row, in a
`scripts/`-prefixed path spelling, or in the trailing shell-leg prose. A module the tree holds but the
map does not name MUST fail the gate, naming that module. The only exemption is the documented
`_SCRIPTS_MAP_EXEMPT` set (the package marker `__init__.py`), and a plain word-only regex must not
capture a phantom basename out of a hyphenated one.

WHEN the census gate runs and a `scripts/*.py` or `scripts/*.sh` file exists at the measured sha but
its basename appears nowhere in the §Scripts section
THEN the gate exits non-zero and names that module.

#### Scenario: an unmapped tree module reddens the gate with its name

- **Given** a tree whose measured sha contains `scripts/orphan_module.py` but whose §Scripts table
  does not name it
- **When** the census gate runs at that sha
- **Then** it exits non-zero and its output names `orphan_module.py`
- **Test:** `tests/test_architecture_census.py::test_a_tree_module_with_no_group_row_reddens_naming_it`

### Requirement: a hyphenated scripts module is read whole, never as its suffix

A scripts module whose basename contains a hyphen (the tree carries `fold-live-profile.py`) MUST be
recognised as ONE name by both directions of the map check, and the plain `\w`-only regex must never
report a phantom `profile.py` out of it. The `scripts/`-prefixed spellings the prose uses
(`scripts/tools/llgenie_harness.py`, `scripts/module_name_guard.py`) MUST resolve to their basenames.

WHEN the census gate reads the §Scripts section
THEN `fold-live-profile.py` is captured whole and no `profile.py` finding is produced.

#### Scenario: the §Scripts section rows a hyphenated module without a phantom finding

- **Given** a §Scripts section containing `` `fold-live-profile.py` ``
- **When** the census gate extracts the section's module names
- **Then** `fold-live-profile.py` is named and `profile.py` is not
- **Test:** the hyphen handling is exercised by the real-tree negative control and the
  `_scripts_coverage_names` extraction in the mapped-tree unit coverage
