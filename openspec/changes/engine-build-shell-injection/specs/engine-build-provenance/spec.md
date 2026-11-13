# Delta spec: engine-build-provenance

## MODIFIED Requirements

### Requirement: Dispatch provenance passes values through env

The engine-build Dispatch provenance step SHALL bind `inputs.producer_run` and
`github.triggering_actor` in its `env:` block and SHALL reference them only as shell
variables inside `run:`. No GitHub expression may appear in the step's shell text.

#### Scenario: injection-shaped dispatch value

- **WHEN** a `workflow_dispatch` sends `producer_run` containing quotes or `$( )`
- **THEN** the provenance step prints it verbatim and executes nothing
- **AND** semgrep `run-shell-injection` reports zero findings at
  `.github/workflows/engine-build.yml`

#### Scenario: lock test holds the shape

- **WHEN** `make test-unit` runs `tests/test_check_engine_pins_published.py`
- **THEN** `test_liveness_dispatches_name_their_producer_run` asserts the provenance
  step's `run:` body contains no GitHub expression and both `PRODUCER_RUN:` /
  `TRIGGERING_ACTOR:` env bindings exist
