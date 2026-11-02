## ADDED Requirements

### Requirement: per-lane-profile-scope

`scripts/check_agent_profiles.py` SHALL accept `--profile <name>` and, when given, report only findings
whose `first-path-segment` identifies `<name>` PLUS the manifest/fleet findings every lane shares,
keeping exit code `1` on any remaining finding, `0` when the scoped set is empty, and `2` when `<name>`
is not a profile the manifest carries.

#### Scenario: a clean lane greens under its own scope despite a drifted sibling

- **Given** a tree with two manifest profiles, one clean and one whose live profile is drifted
- **When** `check --profile <clean>` runs on a host whose live home carries the sibling's drift
- **Then** it exits 0 and names the scope audibly
- **Test:** `tests/test_agent_profiles.py::test_profile_scope_greens_a_clean_lane_despite_another_lanes_drift`

#### Scenario: the scoped view is a strict subset of the global check

- **Given** the same two-profile tree with sibling drift
- **When** `_profile_scope(global_items, profiles, <clean>)` is compared to the global findings
- **Then** every scoped `where` is a member of the global `where` set, and no sibling path appears scoped
- **Test:** `tests/test_agent_profiles.py::test_profile_scope_is_a_subset_of_the_global_findings`

#### Scenario: an unknown profile is a broken invocation

- **Given** a manifest that carries a profile
- **When** `check --profile nobodys-lane` runs
- **Then** it exits 2 and names the invalidity, never a silent pass
- **Test:** `tests/test_agent_profiles.py::test_profile_scope_rejects_an_unknown_lane`

#### Scenario: every committed lane passes its own scope

- **Given** the repository's committed `agents/` tree
- **When** `check --profile <name>` runs for each of the seven committed lanes
- **Then** each exits 0 (live home isolated so a drifted host and CI agree)
- **Test:** `tests/test_agent_profiles.py::test_profile_scope_on_the_committed_tree_is_clean`

### Requirement: committed-tree-ratchet

`scripts/check_agent_profiles.py --ratchet` SHALL refuse a committed-tree finding at a `where` site the
recorded `tests/fixtures/agent-profiles-baseline.json` does not carry, exit `1` when any is refused and
`0` when the current tree scores at or below the baseline, and SHALL read the tree WITHOUT the live-home
comparison so a drifted host cannot move the bar it ratchets against. `--update-baseline` SHALL re-record
the current tree-only findings as the new baseline.

#### Scenario: a new committed-tree finding is refused

- **Given** a clean tree whose baseline records no findings, and an injected finding
- **When** `--ratchet` / `ratchet(root)` runs
- **Then** it reports the new site as refused and exits 1; after `--update-baseline` it exits 0 again
- **Test:** `tests/test_agent_profiles.py::test_ratchet_refuses_a_new_committed_tree_finding`

### Requirement: host-fragile-tests-isolate-the-live-home

The clean-tree tests in `tests/test_agent_profiles.py` SHALL isolate `HERMES_PROFILES_HOME` to an empty
fixture path when they assert a tree-only verdict, so another lane's live drift cannot red a lane's own
profile test (issue #1090).

#### Scenario: the committed-tree and fleet-block tests pass on a drifted host

- **Given** a host whose `~/.hermes/profiles/` carries other lanes' live edits
- **When** the seven formerly host-fragile tests run
- **Then** each passes because it judges only its own fixture's tree
- **Test:** `tests/test_agent_profiles.py` — the isolated variants of the seven clean-tree tests
