# ci-discipline — Spec Delta

## ADDED Requirements

### Requirement: Only allow-listed workflows may declare a schedule

The repository SHALL keep every wall-clock `on.schedule:` block inside the allow-list recorded in
`scripts/check_ci_discipline.py::SCHEDULE_ALLOW`, each entry carrying a written rationale. The
allow-list SHALL include the weekly engine-bump + engine-image lane (`engine-bump.yml`,
`engine-bump-rebase.yml`) and the registry-liveness lane (`registry-liveness.yml`,
`registry-sync.yml`), plus the merge/housekeeping roster already on record. The eight bot lanes
deactivated by issue #2701 (`architecture-bot.yml`, `ci-requeue.yml`, `issue-bot.yml`,
`issue-dedupe.yml`, `issue-refiner.yml`, `registry-sync-review.yml`, `search-smoke.yml`,
`rebase-bot.yml`) SHALL keep their dispatch/push/PR triggers and SHALL NOT carry a `schedule:`.

#### Scenario: a new clock outside the allow-list is a finding

- **Given** a fixture tree that adds an `on.schedule:` block to a workflow not in the allow-list
- **When** `python3 scripts/check_ci_discipline.py check --root <fixture>` runs
- **Then** it exits non-zero and names the offending file

#### Scenario: a stale allow-list entry is a finding

- **Given** a fixture tree where an allow-listed workflow no longer declares any `schedule:`
- **When** the check runs on it
- **Then** it exits non-zero and names the stale entry with its recorded rationale

#### Scenario: the deactivated lanes stay dispatch-only

- **Given** the repository after this change
- **When** each of the eight deactivated workflows is parsed
- **Then** it declares no `schedule:` and keeps its non-schedule triggers

### Requirement: The CI main pipeline is tests-only

`ci.yml`, `pipeline.yml` and `all-pipelines.yml` SHALL carry no Hermes agent leg and no agent-image
job marker. `make check-ci-discipline` SHALL fail when any of them gains one.

#### Scenario: an agent job added to the main pipeline is caught

- **Given** a fixture tree where `ci.yml` carries a job referencing an agent leg marker
- **When** the check runs on it
- **Then** it exits non-zero naming `ci.yml` and the job

### Requirement: Hermes agent legs live only in allow-listed agent lanes

Hermes/LLM usage in CI SHALL be confined to the agent lanes recorded in
`scripts/check_ci_discipline.py::AGENT_LANES` plus the scheduled engine/registry agent-image lanes:
lanes whose purpose is fetching latest engine servers, syncing the registry, updating the engine
list, refreshing Dockerfiles, building/publishing the Hermes agent image (`publish-agent-image.yml`),
and the dispatch-only bot lanes. A workflow outside those lists SHALL NOT reference an agent leg
marker; a deactivated agent lane SHALL NOT re-schedule itself.

#### Scenario: an outside workflow reaches for the agent leg

- **Given** a fixture tree where a workflow outside both allow-lists uses an agent leg marker
- **When** the check runs on it
- **Then** it exits non-zero and names the workflow

#### Scenario: a deactivated agent lane re-schedules

- **Given** a fixture tree where one of the eight deactivated agent lanes declares a `schedule:` again
- **When** the check runs on it
- **Then** it exits non-zero naming the lane and issue #2701

### Requirement: The discipline rule lives in the repo rules file and the gate pins it

AGENTS.md SHALL carry the durable section
`## CI pipeline discipline: weekly engine/registry lane only, tests-only main pipeline, Hermes in
agent-image lanes only (mandatory, durable)`, and `scripts/check_ci_discipline.py` SHALL fail when
the section or any of its pin phrases disappears. The gate SHALL be wired into `mk/gates.mk`, the
`ci-unit` sequence in `scripts/ci_unit.py` (`MAKE_SEQUENCE`, its home since issue #2675),
`scripts/package-layers.json`, and `scripts/issue_bot_gates.py`, and `make check-wiring` SHALL stay
green with it present.

#### Scenario: removing the durable section is a finding

- **Given** a fixture tree whose AGENTS.md lost the CI-discipline section
- **When** the check runs on it
- **Then** it exits non-zero naming AGENTS.md

#### Scenario: the gate is green on the repository

- **Given** the repository at the head of this change
- **When** `make check-ci-discipline` runs
- **Then** it prints `check-ci-discipline: OK` and exits 0
