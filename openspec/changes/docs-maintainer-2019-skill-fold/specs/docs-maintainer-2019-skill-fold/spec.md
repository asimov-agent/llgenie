# docs-maintainer-2019-skill-fold

## ADDED Requirements

### Requirement: Live profile fold is byte-identical to the tree

**When** `make sync-agent-profile PROFILE=llgenie-documentation-maintainer CHECK=1` measures the 10
drifted files (`SKILL.md`, the 6 live-longer references, and the 4 live-only references) between the
live profile and the committed tree

**Then** all report no tree-vs-live diff (tree == live).

#### Scenario: the 10 drifted files match the live profile after the fold

**Given** the docs-maintainer live profile at `/home/asimov/.hermes/profiles/llgenie-documentation-maintainer/`

**When** the tree is measured with `make sync-agent-profile PROFILE=llgenie-documentation-maintainer CHECK=1`

**Then** `SKILL.md`, the six live-longer `references/` files, and the four live-only `references/` files
show no diff (tree == live), and live refs 23 == tree 23.

#### Scenario: the change-note trio is committed

**Given** the fold PR

**When** `docs/changes.d/` and `agent-wiki/` are inspected

**Then** the `2026-11-07-docs-maintainer-2019-skill-fold.md` row exists in both, and `CHANGES.md`
carries the row rendered from the fragment.
