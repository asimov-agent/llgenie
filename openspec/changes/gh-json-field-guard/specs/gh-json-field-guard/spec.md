# gh-json-field-guard

## ADDED Requirements

### Requirement: every `gh … --json` call site in the repo is validated against a captured per-subcommand field allowlist

`make check-gh-json-fields` (`scripts/check_gh_json_fields.py`) MUST scan every `scripts/*.py`
file and every `.github/workflows/*.yml` shell lane for `gh` invocations that pass `--json`,
resolve the requested field names statically, and report a finding for every field that is not in
the allowlist captured from the real gh CLI (`tests/fixtures/gh-json-fields.json`, captured via
`gh <cmd> --json __probe__`). For Python call sites the guard MUST resolve field lists written as
string constants, variables bound to constants, and `",".join(<constant list>)` expressions. The
gate MUST exit non-zero when any finding exists.

#### Scenario: the #513 shape re-synthesized is red

- **Given** a script containing `["gh","pr","view",…,"--json","number,headRefOid,authorAssociation"]`
- **When** `make check-gh-json-fields` runs against a tree carrying it
- **Then** the gate reports an `unknown-field` finding naming `authorAssociation` with file and line
- **Test:** `tests/test_check_gh_json_fields.py::test_the_invalid_author_association_shape_is_red`

#### Scenario: a field assembled from a constant list is caught

- **Given** a script building `--json` fields via `",".join(FIELDS)` where `FIELDS` is a constant
  list carrying an invalid name
- **When** the guard scans it
- **Then** it reports the invalid name as an `unknown-field` finding
- **Test:** `tests/test_check_gh_json_fields.py::test_a_field_built_from_a_constant_list_is_red`

#### Scenario: workflow shell lanes are scanned

- **Given** a workflow lane running `gh pr view "$N" --json headRefOid,bogusField`
- **When** the guard scans `.github/workflows/`
- **Then** it reports `bogusField` as an `unknown-field` finding naming the workflow file and line
- **Test:** `tests/test_check_gh_json_fields.py::test_shell_lane_json_fields_are_scanned`

### Requirement: the guard fails CLOSED on call sites it cannot statically attribute or resolve

A `--json` occurrence the guard cannot tie to a known gh subcommand (an argv list carrying `gh`
with an unknown subcommand pair, or a shell verb the real CLI has no `--json` for, such as
`gh issue create`) MUST be reported as an `unattributable-subcommand` finding, and a `--json`
whose field list cannot be resolved statically (runtime expression in Python, `$`-interpolated in
shell) MUST be reported as an `unresolvable-fields` finding. Neither MAY be silently skipped.
An owned repo script's own `--json`-style CLI flag MUST NOT be reported (only real gh
invocations are against the allowlist).

#### Scenario: a bogus subcommand is a finding, not a skip

- **Given** `["gh","bogus","thing","--json","body"]` in a script
- **When** the guard scans it
- **Then** the site is counted and reported as `unattributable-subcommand`
- **Test:** `tests/test_check_gh_json_fields.py::test_a_json_call_that_cannot_be_attributed_to_a_known_subcommand_is_red`

#### Scenario: `gh issue create --json` is a finding because the verb has no --json

- **Given** a workflow lane running `gh issue create … --json number --jq .number`
- **When** the guard scans it
- **Then** it reports `unattributable-subcommand`
- **Test:** `tests/test_check_gh_json_fields.py::test_gh_issue_create_json_is_a_finding_because_the_verb_has_no_json`

#### Scenario: unresolvable fields are red

- **Given** `["gh","pr","view","1","--json",build_fields()]` or a shell `--json "$FIELDS"`
- **When** the guard scans either
- **Then** each is reported as `unresolvable-fields`
- **Test:** `tests/test_check_gh_json_fields.py::test_unresolvable_fields_are_red_not_skipped`
- **And:** `tests/test_check_gh_json_fields.py::test_shell_lane_json_fields_are_scanned`

#### Scenario: an owned script's own --json flag is not a gh call

- **Given** an owned script declaring `p.add_argument("--json", …)`
- **When** the guard scans it
- **Then** it reports no finding and counts no call site
- **Test:** `tests/test_check_gh_json_fields.py::test_a_repo_owned_argument_like_a_cli_flag_is_scanned`

### Requirement: the committed tree passes the guard and the guard covers the whole measured surface

At every merged head `make check-gh-json-fields` MUST exit zero, and the scan MUST attribute at
least the surface issue #515 measured (≥19 scripts, ≥46 `--json` call sites, across both the
Python and shell lanes). The gate MUST run in `ci-unit` (registered in `ci_unit.MAKE_SEQUENCE`,
classified in `issue_bot_gates.DEFERRED`, grouped in `scripts/package-layers.json`).

#### Scenario: green against the real tree with the measured coverage

- **Given** this repository at the merged head
- **When** `make check-gh-json-fields` runs
- **Then** it exits 0 with zero findings
- **And** its coverage line reports at least 19 scripts and at least 46 call sites
- **Test:** `tests/test_check_gh_json_fields.py::test_the_committed_tree_is_green_and_covers_at_least_the_measured_surface`

#### Scenario: the broken registry-liveness call site is repaired, not just flagged

- **Given** the lane that files tracking issues for unpublished engine tags
- **When** it runs after this change
- **Then** `gh issue create` is invoked without `--json`/`--jq` and the issue number is taken from
  the URL gh prints
- **Test:** `tests/test_check_gh_json_fields.py::test_the_committed_tree_is_green_and_covers_at_least_the_measured_surface`
  (the guard is green, which requires the fix landed)
