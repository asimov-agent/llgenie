## ADDED Requirements

### Requirement: skill-parity (Layer A, host-only, read-only) — issue #1924

The tree SHALL provide `make skill-parity`, a host-only, READ-ONLY target that diffs each
`agents/<profile>/skills/` directory (every manifest llgenie profile) against the live profile's
`skills/` at `~/.hermes/profiles/<profile>/` and prints live-only / tree-only counts and names. It
SHALL NOT write: a run must leave both the live profile and the tree byte-identical, because
`sync-agent-profile`'s write mode truncates silently when live > tree (the measured state). A host
with no live profiles is not a failure (exit 0, no verdict).

#### Scenario: a live-only reference is named, not written

- **Given** a live profile whose `skills/` carries a file the tree does not
- **When** `make skill-parity` runs
- **Then** it prints the live-only count and the file's name, and neither the live profile nor the tree changed after the run
- **Test:** `tests/test_skill_parity.py::test_live_only_and_tree_only_reported` and `test_read_only_never_modified`

#### Scenario: a host without live profiles does not fail

- **Given** a checkout with no `HERMES_PROFILES_HOME` profiles
- **When** `make skill-parity` runs
- **Then** it exits 0 with a "nothing to compare" note (a CI runner's honest answer)
- **Test:** `tests/test_skill_parity.py::test_no_live_profiles_is_not_a_failure`

### Requirement: check-skill-code-parity (Layer B, CI) — issue #1924

The tree SHALL provide `make check-skill-code-parity`, a CI gate that reads every
`agents/*/skills/**/*.md` and fails when a reference cites a test id (`tests/<file>.py::<test>`, a
trailing `...` resolved by prefix, the generic `test_x.py::test_name` template ignored) whose test
file is not in the hermetic suite (`scripts/unit_tests.py` collection) or whose test id is not
defined, or when a backticked repository-owned code symbol does not resolve. Fenced ``` blocks are
quoted logs/commands, not claims, and are not checked. The gate is wired into `ci-unit`
(`scripts/issue_bot_gates.py` DEFERRED classification) and exits 1 on any finding.

#### Scenario: a stale cited test id reds

- **Given** a reference citing `tests/test_x.py::test_that_never_existed`
- **When** `make check-skill-code-parity` runs
- **Then** it exits 1 naming the citation and the missing test
- **Test:** `tests/test_skill_code_parity.py::test_mutation_stale_test_id_reds`

#### Scenario: a test outside the hermetic suite reds

- **Given** a citation whose test file the unit-suite roster excludes
- **When** `make check-skill-code-parity` runs
- **Then** it exits 1 saying the test is not in the hermetic suite (a test that does not run cannot prove the sentence)
- **Test:** `tests/test_skill_code_parity.py::test_suite_excluded_test_reds`

#### Scenario: a broken repository-owned symbol reds; a green anchor passes

- **Given** a reference citing `scripts/this_script_does_not_exist.py`
- **When** `make check-skill-code-parity` runs
- **Then** it exits 1 naming the symbol, while a citation of a real hermetic test (e.g.
  `tests/test_auto_merge.py::test_a_stale_marker_green_head_is_retried_and_merged`) passes
- **Test:** `tests/test_skill_code_parity.py::test_mutation_broken_symbol_reds` and `test_green_anchor_resolves`

### Requirement: the reference correction — issue #1924

`agents/llgenie-planner/skills/llgenie-bot-orchestration/references/auto-merge-mechanism.md` §3 SHALL
state the post-#1914 recheck behaviour: a green head whose deferral marker went stale by a head move
is swept by `recheck` (`scripts/auto_merge.py::has_any_deferral_marker`), doomed only by concurrency,
never by dedupe-as-skip, and SHALL anchor that claim to
`tests/test_auto_merge.py::test_a_stale_marker_green_head_is_retried_and_merged`. The file was
live-only (not on main) and is committed in this change.

#### Scenario: the reference documents the fixed behaviour, not the bug

- **Given** the reference's stale-by-move paragraph
- **When** it is read
- **Then** it describes the recheck sweep that catches a green moved head (post-#1914), not "skipped by every cron run", and names the proving test
- **Test:** `make check-skill-code-parity` on the corrected tree passes (0 findings), and §3 text asserts the sweep
