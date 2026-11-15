# ci-discipline — delta for the dispatch roster

## MODIFIED Requirements

### Requirement: The discipline rule lives in the repo rules file and the gate pins it

AGENTS.md SHALL carry the durable section
`## CI pipeline discipline: weekly engine/registry lane only, tests-only main pipeline, Hermes in
agent-image lanes only (mandatory, durable)`, and that section SHALL state the agent's mode and
the starters: the agent **verifies locally with `make`** (runs the Makefile gates on its own
tree) and never starts a GitHub CI pipeline for its own work; a CI pipeline starts from a GitHub
event, **or from a dispatch a permitted principal starts — the owner, a collaborator, and GitHub
itself (the Actions bot)**, or from a scheduled (cron) lane. The same section SHALL keep the
queue-pumping ban for the automated agent (no `gh run rerun`, no requeue or re-trigger loops; a
wedge is fixed by pushing a commit) and SHALL name the one exception: an agent may start a
dispatch to **test a workflow that is failing** — debugging the pipeline itself — and only for
that. `scripts/check_ci_discipline.py` SHALL fail when the section
or any of its pin phrases disappears, and its pin phrases SHALL name all halves: the roster, the
queue-pumping ban, the local-`make` verification mode, and the failing-workflow exception. The
gate SHALL be wired into `mk/gates.mk`, the `ci-unit` sequence in `scripts/ci_unit.py`
(`MAKE_SEQUENCE`, its home since issue #2675), `scripts/package-layers.json`,
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

#### Scenario: the agent's local-make mode and the exception are named in the rules

- **Given** the repository's real AGENTS.md CI-discipline section
- **When** the gate pins its phrases
- **Then** the pinned phrases include the verification mode ("verifies locally with `make`") and the exception ("test a workflow that is failing")
- And a fixture tree that replaces the mode sentence with an agent-dispatches-its-own-lane wording is a finding naming AGENTS.md

#### Scenario: the gate is green on the repository

- **Given** the repository at the head of this change
- **When** `make check-ci-discipline` runs
- **Then** it prints `check-ci-discipline: OK` and exits 0
