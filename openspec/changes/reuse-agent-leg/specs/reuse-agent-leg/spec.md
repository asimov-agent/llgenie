# reuse-agent-leg — spec of record

## ADDED Requirements

### Requirement: the agent-leg preflight lives in ONE composite action

The repository MUST provide a composite action `.github/actions/agent-leg/action.yml`
whose steps are the ordered agent-leg preflight — `make agent-jev-preflight`
(issue #238), `make agent-shell-keys-check` (issue #358) and, when the caller
opts in, `make hermes-smoke` (issue #407) — plus the REDACTED-transcript upload
(issue #359). These steps MUST NOT be inlined in any `.github/workflows/*.yml` bot
leg.

#### Scenario: the preflight steps exist once
- **WHEN** the tree is scanned for `make agent-jev-preflight` and
  `make agent-shell-keys-check`
- **THEN** both invocations appear only inside `.github/actions/agent-leg/action.yml`
  (and in `scripts/check_workflows.py`'s inline-detector literals), never inside a
  `.github/workflows/*.yml` job

#### Scenario: a caller controls the routing smoke
- **WHEN** a leg passes `routing-smoke: true` to the composite action
- **THEN** the composite action runs `make hermes-smoke`; when it passes
  `routing-smoke: false` the smoke does not run

### Requirement: a reusable agent-leg workflow exists

The repository MUST provide `.github/workflows/agent-leg.yml` triggered by
`on.workflow_call`, declaring the leg-shaped inputs (`target`, `skill`, `push`,
`timeout`, `transcript` and the checkout shape) and running one agent leg job that
checks out, runs the preflight through the composite action, runs the `make
target` the caller names, and uploads the REDACTED transcript.

#### Scenario: a plain leg runs through the reusable workflow
- **WHEN** a caller's job `uses: ./.github/workflows/agent-leg.yml` with a `target`
- **THEN** the reusable workflow's job runs the preflight and the named `make`
  target and uploads the REDACTED transcript, with the job's own `timeout-minutes`
  (a `uses:` job may not carry one — issue #882)

### Requirement: a bot leg that inlines the preflight reddens check-workflows

`scripts/check_workflows.py check` MUST report a `.github/workflows/*.yml` bot leg
whose steps inline BOTH `make agent-jev-preflight` and `make agent-shell-keys-check`
(instead of calling the composite action), and `make check-workflows` MUST exit
non-zero on it. The gate MUST stay green when the six agent legs call the reusable
preflight.

#### Scenario: an unmigrated leg is caught
- **WHEN** a workflow's job steps contain both `make agent-jev-preflight` and
  `make agent-shell-keys-check`
- **THEN** `check_workflows.py check` lists it and exits non-zero

#### Scenario: the migrated legs pass
- **WHEN** every agent leg calls `.github/actions/agent-leg` for its preflight
- **THEN** `check_workflows.py check` exits 0

### Requirement: scrub_log.py is unchanged

The redaction script `scripts/scrub_log.py` MUST NOT change as part of this work.

#### Scenario: the redaction seam is untouched
- **WHEN** the change lands
- **THEN** `scripts/scrub_log.py` has no diff from `main`
