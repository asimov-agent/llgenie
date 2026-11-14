## ADDED Requirements

### Requirement: One installer seam populates every lane home from the tree

The repository SHALL install every fleet lane declared in `agents/manifest.json` into a Hermes profile home through exactly one implementation — `scripts/provision_agent_profiles.py`, the wrapper over the `agent_profile_sync` write/check primitives. The agent image build and the host SHALL both invoke it; no lane SHALL be populated by a hand-rolled `cp` loop.

#### Scenario: the agent image installs lanes through the seam

- **WHEN** the agent image build runs its lane-install step
- **THEN** the step invokes `provision_agent_profiles.py --root /opt/llgenie --dest ${HERMES_HOME}/profiles --resolve` and the build fails non-zero when any declared lane is missing, unwritable, or fails the write-then-read-back reconciliation

#### Scenario: the host installs the same lanes through the same seam

- **WHEN** `make provision-agent-profiles` runs on the host
- **THEN** the same script installs every manifest lane into the host's Hermes profile homes with the same reconciliation guarantees

### Requirement: Installed lanes are reconciled byte-for-byte against the tree

After a write the installer SHALL verify, for every declared lane, that every file the tree carries matches the installed home byte-for-byte, naming every differing or missing relative path and exiting non-zero.

#### Scenario: drift is named, never silent

- **WHEN** a lane home written by the installer fails the read-back comparison against the tree
- **THEN** the installer names the lane and exits non-zero, failing the image build that ran it

### Requirement: Hermes resolves each lane's skills at build time

The installer's `--resolve` mode SHALL prove, for every declared lane, that each skill the lane's tree carries (`skills/**/SKILL.md`, named by its directory) is resolvable by Hermes for that lane via `hermes -p <lane> skills list --source local`, failing with the lane and the missing skill named. The resolver SHALL be injectable so unit tests exercise the logic without the CLI, and the CLI path SHALL fail loudly (non-zero, named) when `hermes` is not installed.

#### Scenario: a skill the tree carries but Hermes cannot resolve fails the build

- **WHEN** resolve mode runs for a lane and a tree skill name is absent from the lane's resolved skill list
- **THEN** the installer names the lane and the skill and exits non-zero

### Requirement: The build gate sees skill subtree drift

`scripts/agent_lanes_check.py` SHALL report, as build findings, a declared lane whose installed home lacks a `skills/` subtree the tree carries, and any tree `SKILL.md` file missing from or byte-differing in the installed home, naming the lane and the relative path.

#### Scenario: a lane installed with only SOUL.md fails the gate

- **WHEN** the gate compares a tree lane that carries `skills/<name>/SKILL.md` against an installed home that has `SOUL.md` but no `skills/`
- **THEN** the gate exits non-zero naming the lane and the missing skill file

### Requirement: Scripts the image build runs are image hash inputs

Every script the agent image build executes SHALL be listed in that image's hash inputs in `scripts/ci_images.py`, so editing the installer or the gate moves the agent image tag.

#### Scenario: an installer edit moves the agent image tag

- **WHEN** `scripts/provision_agent_profiles.py` or `scripts/agent_lanes_check.py` changes
- **THEN** the agent image hash computed by `scripts/ci_images.py` changes with it

### Requirement: Hermes cron jobs never run on the host

`AGENTS.md` SHALL state, as a durable behavior rule, that Hermes profile cron jobs never dispatch on the host: every profile cron store stays empty or paused, the kanban worker pool stays closed, and scheduled bot legs exist only as CI `schedule:` lanes running the fleet image. Interactive agent work on the host proceeds one issue/PR at a time.

#### Scenario: the rule is in the behavior file

- **WHEN** `AGENTS.md` is read on `main` after this change
- **THEN** it carries the heading "Hermes cron jobs never run on the host (MANDATORY, durable)" with the empty-cron-store, closed-worker-pool, and one-task-at-a-time statements

### Requirement: The change is covered by unit tests running in main CI

The installer's resolve mode and the deepened gate SHALL have unit tests that run in the main CI unit stage against fixture trees, without network or a Hermes installation.

#### Scenario: the main CI unit stage runs the harness tests

- **WHEN** the main CI unit stage executes the repository test suite
- **THEN** `tests/test_provision_agent_profiles.py` and `tests/test_agent_lanes_check.py` cover resolve findings, gate skill findings, and reconciliation regressions, and any such regression fails that stage
