# engine-improver-live-ref-fold

## ADDED Requirements

### Requirement: Live profile fold is byte-identical to the tree

**When** `make sync-agent-profile PROFILE=llgenie-engine-improver CHECK=1` measures the five drifted files
(`ci-run-watching.md`, `image-layer-caching.md`, `pr-gate-and-rebase-recovery.md`, `proving-and-pitfalls.md`,
`agent-profile-soul.md`) between the live profile and the committed tree

**Then** all five report no tree-vs-live diff (tree == live).

#### Scenario: the five drifted files match the live profile after the fold

**Given** the engine-improver live profile at `/home/asimov/.hermes/profiles/llgenie-engine-improver/`

**When** the tree is measured with `make sync-agent-profile PROFILE=llgenie-engine-improver CHECK=1`

**Then** the four `references/` files and `agent-profile-soul.md` show no diff (tree == live).

#### Scenario: the change-note trio is committed

**Given** the fold PR

**When** `docs/changes.d/` and `agent-wiki/` are inspected

**Then** the `2026-11-05-engine-improver-live-ref-fold-1740.md` row exists in both, and `CHANGES.md` carries
the row rendered from the fragment.
