## ADDED Requirements

### Requirement: The chain's catalog membership is checked weekly

The repository SHALL ship `scripts/check_agent_model_catalog.py` and a make
target `check-agent-model-catalog` that compare the chain declared in
`agents/hermes-base-config.yaml` (the primary `model:` block and every
`fallback_providers` entry) against the Nous model catalog
(`GET https://inference-api.nousresearch.com/v1/models`, public, no auth).
The check SHALL exit 0 when every chain id is listed AND every committed
`context_window` equals the catalog's published `context_length` for that id;
otherwise it SHALL exit non-zero naming each missing member and each budget
divergence. `--catalog <file>` SHALL read a saved catalog payload instead of
the network, and `--dry-run` SHALL print the would-be issue body without
filing anything. The check SHALL read no credential and send no header it
could not send publicly.

#### Scenario: all five members listed
- **WHEN** the fetched catalog contains all five `:free` ids with matching
  `context_length`
- **THEN** the target exits 0 and prints the per-member match lines

#### Scenario: a member left the catalog
- **WHEN** a fixture catalog lacks one chain id
- **THEN** the check exits non-zero naming that id

#### Scenario: a budget diverges
- **WHEN** a committed `context_window` differs from the catalog's
  `context_length` for that id
- **THEN** the check exits non-zero naming the divergence with both numbers

### Requirement: Findings file ONE deduped issue

The checker SHALL file exactly one issue for its findings using
`scripts/issue_body.py::render` with the producer marker as the body's first
line, labelled `agent:implement`, naming the catalog's current `:free` ids as
replacement candidates. A later run SHALL find its marker among OPEN issues
(body search, never a page scan) and update that issue instead of filing a
duplicate; the marker read-back SHALL be loud when the search fails. The
producer SHALL be listed in `issue_body.PRODUCERS`.

#### Scenario: dry-run shape
- **WHEN** `--dry-run` runs against a catalog missing one id
- **THEN** stdout carries the marker line, the six-section body, the missing
  id, and no credential

### Requirement: The wiring stays inside the allow-listed weekly lane

The check SHALL run as a step of the weekly `registry-sync.yml` sync job only.
The change SHALL NOT add a new `on.schedule:`, SHALL NOT add an agent leg or
agent-image job to any workflow, and `make check-ci-discipline` SHALL pass on
the resulting tree, with the lane's `SCHEDULE_ALLOW` rationale naming the
catalog check.

#### Scenario: discipline gate
- **WHEN** `make check-ci-discipline` runs on the tree carrying this change
- **THEN** it exits 0
