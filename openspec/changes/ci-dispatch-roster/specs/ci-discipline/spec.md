# ci-discipline — delta for the dispatch roster

## MODIFIED Requirements

### Requirement: The discipline rule lives in the repo rules file and the gate pins it

AGENTS.md SHALL carry the durable section
`## CI pipeline discipline: weekly engine/registry lane only, tests-only main pipeline, Hermes in
agent-image lanes only (mandatory, durable)`, and that section SHALL state the dispatch roster:
a CI pipeline starts from a GitHub event, **or from a dispatch a permitted principal starts —
the owner, a collaborator, and GitHub itself (the Actions bot)**. The same section SHALL keep the
queue-pumping ban for the automated agent (no `gh run rerun`, no requeue or re-trigger loops; a
wedge is fixed by pushing a commit). `scripts/check_ci_discipline.py` SHALL fail when the section
or any of its pin phrases disappears, and its pin phrases SHALL name both halves: the roster and
the queue-pumping ban. The gate SHALL be wired into `mk/gates.mk`, the `ci-unit` sequence in
`scripts/ci_unit.py` (`MAKE_SEQUENCE`, its home since issue #2675), `scripts/package-layers.json`,
and `scripts/issue_bot_gates.py`, and `make check-wiring` SHALL stay green with it present.

#### Scenario: removing the durable section is a finding

- **Given** a fixture tree whose AGENTS.md lost the CI-discipline section
- **When** the check runs on it
- **Then** it exits non-zero naming AGENTS.md

#### Scenario: the dispatch roster is named in the rules

- **Given** the repository's real AGENTS.md CI-discipline section
- **When** the gate pins its phrases
- **Then** the pinned phrases include the roster ("owner, a collaborator, and GitHub itself") and the forbidden queue-pumping (`gh run rerun`)
- And the blanket-ban phrase "never manually starts a CI pipeline" is no longer required by the gate

#### Scenario: the gate is green on the repository

- **Given** the repository at the head of this change
- **When** `make check-ci-discipline` runs
- **Then** it prints `check-ci-discipline: OK` and exits 0
