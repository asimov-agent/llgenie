## ADDED Requirements

### Requirement: The lane profiles reference points at the fleet-memory doc

Every lane profiles reference the lanes preload (`agents/*/skills/*/references/agent-profiles*.md`)
SHALL contain a link to the `docs/BOTS.md` section "Fleet memory: one Hindsight daemon per host,
shared plugin profile (issue #2057)", so a lane finds the host memory topology from the skill it
preloads.

#### Scenario: the preloaded reference carries the pointer

- **WHEN** the tree is read at `agents/llgenie-ci-pipelines-maintainer/skills/llgenie-pipeline-maintenance/references/agent-profiles.md`
- **THEN** it links to the `docs/BOTS.md` Fleet memory anchor
  `#fleet-memory-one-hindsight-daemon-per-host-shared-plugin-profile-issue-2057`

#### Scenario: removing the pointer is caught

- **WHEN** the Fleet memory link is deleted from a preloaded reference
- **THEN** the unit suite fails naming the file and the missing link (hermetic, no network)
