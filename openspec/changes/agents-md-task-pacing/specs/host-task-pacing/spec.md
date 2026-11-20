## ADDED Requirements

### Requirement: AGENTS.md states the host-side task-pacing rule

`AGENTS.md` SHALL carry a section titled "Host-side task pacing (MANDATORY, durable)" that names all four behaviors: (1) the agent works exactly one issue/PR at a time on the host; (2) after pushing a lane, the agent SHALL NOT foreground-wait for its CI pipeline to finish; (3) the wait for a CI run SHALL be set as a background watching task (a poll loop that reports the run's completion); (4) the agent SHALL move immediately to the next issue/PR while CI runs and return to the board afterwards to poll until every PR is green and armed.

#### Scenario: fresh session reads the pacing rule

- **WHEN** an agent session opens `AGENTS.md` on `main`
- **THEN** the file contains the "Host-side task pacing (MANDATORY, durable)" section naming all four behaviors

### Requirement: AGENTS.md names the #2526 start-surface gate rules

`AGENTS.md` §"Every workflow file is validated before it can merge" SHALL carry a bullet stating the machine-checked start-surface gate: every `.github/workflows/*.yml` is classified by its start surface (PR-creation chain and its `workflow_run` followers, merge-to-main push, cron, manual dispatch); every file declares an explicit top-level `permissions:` with `write-all` refused (R1); `pull_request_target` is banned (R2); every outsider-reachable trigger carries the `github.triggering_actor` guard outside `run:` script text or derives it transitively through a `workflow_run` roster of already-guarded workflows, as a fixed point where cycles are not trust (R3); manual starts, pushes and crons are write-capable-only at the platform level and need no guard; the fleet state is zero exemptions. The bullet SHALL match the wording of the `docs/BOTS.md` #2526 paragraph.

#### Scenario: fresh session knows the start-surface rules before authoring

- **WHEN** an agent session authors or edits a `.github/workflows/*.yml` file after reading `AGENTS.md`
- **THEN** the instruction file already names R1/R2/R3 and the zero-exemption fleet state, so the workflow is drafted gate-compliant

#### Scenario: documentation gates accept the additions

- **WHEN** `make check-docs` and `make lint` run on the change branch
- **THEN** both exit 0 and the lane carries an agent-wiki entry plus a `docs/changes.d/` fragment referencing the issues and the PR
