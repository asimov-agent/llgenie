## ADDED Requirements

### Requirement: Drift-flagged profile lanes are reconciled by a measured fold or sync, never by a blind write
For every lane flagged by `make -s check-agent-profiles`, the reconciliation SHALL be chosen by a
line-set comparison between the live file and the tree's whole lane store (SKILL.md plus its
`references/`), and the chosen direction SHALL lose no rule text. When the tree already carries the
live-only text (inlined into a SKILL.md or held in a `references/` file), the tree is authoritative and
the reconciliation is a deliberate `make sync-agent-profile PROFILE=<lane> FORCE=1` (the knob `mk/agents.mk` implements) whose refusal reason
(shrink or newer-live) is answered by that recorded comparison. When the live side holds a duplicate
identity of a versioned skill (a flat shadow of a category copy), the reconciliation SHALL remove the
shadow on the live side and SHALL NOT add a second tree copy.

#### Scenario: engine-improver inline equals the versioned reference
- **Given** the live `llgenie-engine-improver` SKILL.md inlines a 404-line block and the tree holds the
  same block in `references/test-ci-refactor-method.md`
- **When** the line-set comparison runs at the lane's head
- **Then** the live block contributes zero lines the tree lacks, the tree's SKILL.md and reference each
  stay under the 100,000-character writer limit, and the lane's post-land sync loses no rule text

#### Scenario: docs stale-snapshot rule is already versioned
- **Given** the live `llgenie-docs-maintainer` SKILL.md carries the stale-snapshot rule inline and the
  tree carries the same rule in `references/merged-ci-verification.md`
- **When** the lane reconciles
- **Then** the tree stays the split (cap-safe) shape, the sync records `1.0.25`, and the gate prints no
  finding naming `llgenie-documentation-maintainer`

#### Scenario: stale live recipe loses to the tree
- **Given** the live `llgenie-pr-review` recipe still names the retired `ci-requeue.yml` lane while the
  tree names `.github/workflows/ci-verdict.yml`
- **When** the lane reconciles
- **Then** the live copy is replaced by the tree's line (tree→live), never the reverse, and the gate
  prints no finding naming `llgenie-pr-reviever`

#### Scenario: a duplicate-identity shadow is removed, not versioned
- **Given** the live `llgenie-issse-implementer` profile holds `skills/bulk-mechanical-migration/`
  (9,327 b) while the same skill identity is versioned in the tree at its category path
- **When** the lane reconciles
- **Then** the tree keeps exactly one copy of the identity, the live shadow is removed, and
  `test_no_lane_tree_carries_the_same_skill_identity_twice` exits 0

### Requirement: The vehicle question is answered by the fold-lane pattern and an audit command
The fleet SHALL record lessons through fold lanes that turn live-profile drift into issue-tracked PRs
under `agents/<profile>/`, and the drift SHALL be measurable at any time: `make check-agent-profiles`
fails on live-only files or directories and `make agent-profiles-report` prints each lane's skills and
every finding. No new per-sentence mechanism is required while those lanes and the audit command exist.

#### Scenario: the 1079 acceptance items map to shipped artifacts
- **Given** issue #1079 asks for the method committed in the tree, a cheap legal vehicle, and an audit
  command
- **When** its acceptance is checked against `main`
- **Then** `git merge-tree`/`ratchet`/fork-fetch discipline is present in
  `agents/llgenie-engine-improver/skills/llgenie-engine-improver/references/test-ci-refactor-method.md`,
  the fold-lane sequence (#2882, #2878, #2884) is the standing vehicle, and
  `make agent-profiles-report` runs — at which point #1079 is closed as decided
