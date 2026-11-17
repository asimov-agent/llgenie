## ADDED Requirements

### Requirement: The issse-implementer bulk-migration skill is versioned in the tree exactly once
The tree SHALL carry the lane's `bulk-mechanical-migration` skill identity exactly once, at
`agents/llgenie-issse-implementer/skills/software-development/bulk-mechanical-migration/`, byte-identical
to the live profile's copy at its own path, so the lane's migration rulebook is reviewable and a later
`make sync-agent-profile PROFILE=llgenie-issse-implementer` can never drop it. The live profile's flat
shadow directory `skills/bulk-mechanical-migration/` SHALL NOT gain a second tree copy: Hermes reads a
lane's whole skills tree as one store, and a duplicate of the same frontmatter name is the #2836
identity collision that `tests/test_provision_agent_profiles.py::test_no_lane_tree_carries_the_same_skill_identity_twice`
reddens.

#### Scenario: fold completeness
- **Given** the live profile holds the skill twice (a flat shadow and a category copy identical to
  the tree's)
- **When** the fold is applied and `make sync-agent-profile PROFILE=llgenie-issse-implementer CHECK=1`
  runs at the committed head
- **Then** the check exits 0, names no TRUNCATED file for this lane, and
  `test_no_lane_tree_carries_the_same_skill_identity_twice` exits 0

#### Scenario: gate verdict for the lane
- **Given** the repository at a head that carries the folded skill
- **When** `make -s check-agent-profiles` runs on a host whose live profiles are the lane's
- **Then** the gate prints no `FAIL` row mentioning `llgenie-issse-implementer`

### Requirement: The fold never writes the live side
The fold SHALL copy live→tree only (bytes-only copy after a stable double-read, destination re-hash
proving identity). It SHALL NOT edit any live profile file and SHALL NOT run a writing
`sync-agent-profile` on this lane before the fold merges.

#### Scenario: direction of the fold
- **Given** a live-only shadow flagged `absent-from-tree` whose skill identity is already versioned
  under its category path
- **When** the lane's fold PR lands
- **Then** the live profile is untouched by the lane's own actions and the tree keeps the single
  category copy with the live bytes (`version: 1.0.0` remains its versioned value) — no second copy
  is added at the shadow path
