# scripts-package-layers

## ADDED Requirements

### Requirement: the layering of `scripts/` is declared as data

`scripts/package-layers.json` MUST place every module of `scripts/` (every `scripts/*.py` except the
package marker `__init__.py`) in exactly one of the five groups `docs/ARCHITECTURE.md` §Scripts
states: Product path, Security pipeline, Structural gates, CI entrypoints, Bots and automation. It
MUST also list every import that crosses a group border, each entry naming its `from`, its `to` and a
non-empty one-line reason.

WHEN a module of `scripts/` is in no group,
THEN the gate names it as `unknown-module` and exits 1.

WHEN a group names a module the tree no longer contains,
THEN the gate names it as `missing-module` and exits 1.

WHEN a module is placed in more than one group,
THEN the gate names it as `duplicate-module` and exits 1.

WHEN a group key is not a row label of the §Scripts table in `docs/ARCHITECTURE.md`,
THEN the gate names it as `unknown-group` and exits 1.

#### Scenario: every module of the real tree has a group

- **Given** the committed `scripts/package-layers.json` and the committed `scripts/` tree
- **When** the file's module set is compared with the tree's module set
- **Then** the two sets are equal — nothing unplaced, no placement the tree lost
- **Test:** `tests/test_package_layers.py::test_the_data_file_names_every_module_of_the_tree`

#### Scenario: a module the file does not place is refused

- **Given** a temp tree whose `scripts/` holds a module no group names
- **When** the gate reads it
- **Then** it reports `unknown-module` and exits 1
- **Test:** `tests/test_package_layers.py::test_a_module_the_file_does_not_place_is_fatal`

#### Scenario: a placement the tree lost is refused

- **Given** a temp tree whose data places a module that does not exist
- **When** the gate reads it
- **Then** it reports `missing-module`
- **Test:** `tests/test_package_layers.py::test_a_placement_the_tree_lost_is_fatal`

#### Scenario: a module placed in two groups is refused

- **Given** a temp tree whose data places one module in two groups
- **When** the gate reads it
- **Then** it reports `duplicate-module`
- **Test:** `tests/test_package_layers.py::test_a_module_in_two_groups_is_fatal`

### Requirement: the gate refuses a cycle, an unstated crossing, and a stale exception

`make check-package-layers` MUST run `scripts/check_package_layers.py check` and MUST be reached by
`make ci-unit`. The gate MUST refuse: an import cycle of more than one module, whether or not it
crosses a group border; a cross-group import absent from `allowed_edges`; an `allowed_edges` entry
the tree no longer contains, or one whose two modules now share a group; and an allowlist entry with
no reason. Data the gate cannot read MUST exit 2, never 0.

WHEN an import cycle exists in `scripts/`,
THEN the gate reports `cycle` and exits 1.

WHEN a module imports across a group border and no allowlist entry states that edge,
THEN the gate reports `cross-group` and exits 1.

WHEN an allowlisted edge is not an edge of the tree any more,
THEN the gate reports `stale-edge` and exits 1.

WHEN the layering data is missing or is not valid JSON,
THEN the gate exits 2.

#### Scenario: a cycle is fatal inside one group

- **Given** a temp tree whose two modules in the SAME group import each other
- **When** the gate reads it
- **Then** it reports `cycle`, because a border never legalises a cycle
- **Test:** `tests/test_package_layers.py::test_a_new_cycle_is_fatal`

#### Scenario: a function-local reverse import is counted as an edge

- **Given** a temp tree whose cycle's reverse edge sits inside a function body
- **When** the gate reads it
- **Then** it reports `cycle` — the shape the issue was filed for
- **Test:** `tests/test_package_layers.py::test_a_function_local_import_is_an_edge`

#### Scenario: an unstated cross-group import is fatal

- **Given** a temp tree whose module imports across a border with no allowlist entry
- **When** the gate reads it
- **Then** it reports `cross-group` and exits 1
- **Test:** `tests/test_package_layers.py::test_a_cross_group_import_absent_from_the_file_is_fatal`

#### Scenario: the same crossing, stated with a reason, is allowed

- **Given** the same crossing, now listed in `allowed_edges` with a reason
- **When** the gate reads the tree
- **Then** it exits 0
- **Test:** `tests/test_package_layers.py::test_a_stated_cross_group_edge_is_allowed`

#### Scenario: an allowlisted edge the tree lost is fatal

- **Given** a temp tree whose allowlist names an edge no module makes any more
- **When** the gate reads it
- **Then** it reports `stale-edge`
- **Test:** `tests/test_package_layers.py::test_an_allowlisted_edge_that_no_longer_exists_is_fatal`

#### Scenario: an allowlist entry with no reason is refused

- **Given** a temp tree whose allowlisted edge carries a blank reason
- **When** the gate reads it
- **Then** it reports `stale-edge`
- **Test:** `tests/test_package_layers.py::test_an_allowlisted_edge_needs_a_reason`

#### Scenario: unreadable data is exit 2, never a pass

- **Given** a temp tree with no layering file
- **When** the gate runs
- **Then** it exits 2
- **Test:** `tests/test_package_layers.py::test_unreadable_data_is_exit_2_never_a_pass`

#### Scenario: the repository tree passes its own gate

- **Given** the real checkout
- **When** `make check-package-layers` runs
- **Then** it exits 0 and prints `check-package-layers: OK`
- **Test:** `tests/test_package_layers.py::test_the_repository_tree_passes_its_own_layering_gate`;
  CI job `linux / unit` -> `make ci-unit` -> `make check-package-layers`

### Requirement: the bump pipeline imports in one direction

The release-archive step MUST live in `scripts/engine_release_archive.py`, below both
`engine_bump` and `engine_params_derive`. `engine_bump` MUST re-export the moved names so its
public surface is unchanged, and `engine_params_derive` MUST NOT import `engine_bump`.

WHEN `scripts.engine_params_derive` is imported in a fresh interpreter,
THEN `scripts.engine_bump` is not in `sys.modules`.

WHEN `scripts/engine_bump.py --help` runs,
THEN it prints its usage and exits 0.

#### Scenario: importing the derive pipeline does not pull in the bump pipeline

- **Given** a fresh interpreter
- **When** it imports `scripts.engine_params_derive`
- **Then** `scripts.engine_bump` is absent from `sys.modules`
- **Test:** `tests/test_package_layers.py::test_derive_imports_without_engine_bump`

#### Scenario: the bump module still imports and runs its CLI

- **Given** the bump module's command line
- **When** `python3 scripts/engine_bump.py --help` runs
- **Then** it prints its usage and exits 0
- **Test:** `tests/test_package_layers.py::test_engine_bump_still_imports_and_runs_its_cli`

#### Scenario: the moved step has one owner, re-exported

- **Given** `scripts.engine_bump` and `scripts.engine_release_archive`
- **When** the names the bump module exposes are compared with the moved module's
- **Then** they are the same objects, not copies
- **Test:** `tests/test_package_layers.py::test_the_moved_release_step_is_the_same_one_engine_bump_exports`

### Requirement: the document states the seam

`docs/ARCHITECTURE.md` §Scripts MUST name `scripts/package-layers.json` and
`make check-package-layers` beside the group table, MUST row the two new modules
(`engine_release_archive.py`, `check_package_layers.py`), and `make check-docs` MUST stay green.

WHEN the §Scripts section is read,
THEN it names the data file and the gate target.

#### Scenario: the architecture document names the file and the target

- **Given** `docs/ARCHITECTURE.md`
- **When** its §Scripts section is read
- **Then** it contains `scripts/package-layers.json` and `check-package-layers`
- **Test:** `tests/test_package_layers.py::test_the_doc_names_the_file_and_the_target`; `make check-docs`
