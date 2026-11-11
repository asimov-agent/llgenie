# Spec delta: agent-profile-parity (llgenie-planner lane)

## ADDED Requirements

### Requirement: Planner live parity is measured and resolved file-by-file

The `llgenie-planner` live profile and the repository tree copy under
`agents/llgenie-planner/` SHALL be byte-identical, and every differing file SHALL
carry a recorded resolution (live kept, tree kept, or merged) with a reason before
a sync is run. A file whose tree copy is the shorter one SHALL NOT be synced
tree→live until the tree copy is fixed first.

#### Scenario: CHECK reports zero differences

- **Given** the folded and synced planner lane has completed under issue #2479
- **When** `make sync-agent-profile PROFILE=llgenie-planner CHECK=1` is run at the fixing head
- **Then** the command exits 0 and reports 0 differing files
- **And** the run output is recorded on issue #2479

#### Scenario: Live-longer findings are resolved by decision, not blind sync

- **Given** a differing planner file whose live copy is the longer one
- **When** the lane resolves it
- **Then** the recorded reason states whether the live bytes are live behaviour
  (fold live→tree) or vendor text the fold intentionally sanitized (tree kept)
- **And** the decision is visible in `agent-wiki/`

#### Scenario: Tree-only updates reach the live profile

- **Given** a planner prompt or script exists in the tree but not (current) in the live profile
- **When** the lane's final sync runs from a head whose tree copies are complete
- **Then** the file is present in the live profile byte-identically
- **And** `CHECK=1` no longer reports it as tree-only or differing
