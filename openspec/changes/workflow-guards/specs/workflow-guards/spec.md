# workflow-guards

## ADDED Requirements

### Requirement: every dispatchable workflow carries the same write-level trigger guard

A workflow a human can start with `Run workflow` MUST refuse anyone who is not the repo owner or a
collaborator with `admin|maintain|write` permission, checking BOTH `github.actor` and
`github.triggering_actor`, before any secret is read. An any-collaborator check (a `curl` expecting `204`
from `/collaborators/<user>`, which read/triage collaborators also get) or an actor-only check MUST be a
test failure. The refusal MUST be the guarding step's non-zero exit. The guard step — its `name:`, `env:`
and `run:` — MUST be byte-identical in every guarded workflow, so one fix cannot miss a copy of the rule.

WHEN a dispatchable workflow is added, a guard is weakened, or one guard drifts from the others
THEN `make test-unit` fails, naming the workflow and the rule it broke.

#### Scenario: the ten dispatchable workflows share one guard body

- **Given** every workflow whose `on:` includes `workflow_dispatch` (ten of them), plus `ci.yml`, which
  is guarded although no human dispatches it
- **When** its run steps are read
- **Then** each guard is the SAME body — `/collaborators/<u>/permission` for `actor` and
  `triggering_actor`, accepting exactly `admin`, `maintain` and `write`, refusing with a non-zero exit
- **And** no guard retains the `204` form
- **Test:** `tests/test_workflow_guards.py::test_every_dispatchable_workflow_has_the_guard`,
  `tests/test_workflow_guards.py::test_the_guard_checks_both_actors_and_a_write_level` and
  `tests/test_workflow_guards.py::test_every_guard_step_is_byte_identical`

### Requirement: the guard gates the work it guards

A `guard` job MUST be a `needs` of the job it protects (directly or transitively), and a step-level guard
MUST sit in a job that can only start from a `workflow_dispatch`. A guard nothing depends on MUST fail the
test — protecting nothing is not protection.

WHEN a workflow declares a guard no job needs, or a guarded job can also run on another event
THEN the test names it.

#### Scenario: a guard nothing needs is a failure

- **Given** each dispatchable workflow and its job graph
- **When** the guard's consumers are resolved
- **Then** every workflow has at least one, or a dispatch-only guarded job (fix-bot)
- **Test:** `tests/test_workflow_guards.py::test_the_guard_actually_gates_the_work`

### Requirement: a guard declares no output nobody reads

A `guard` job MUST NOT declare an output that no job consumes: the refusal is the non-zero exit, and a
declared-but-unread `outputs.allowed` makes a reviewer believe a value is consulted. The rule MUST be
checked over EVERY workflow, not only the dispatchable ones (the finding was `ci.yml`, which nobody
dispatches).

WHEN a guard declares an output
THEN some job's `if:` references `needs.guard.outputs.<key>`, or the test fails.

#### Scenario: ci.yml's dead output stays gone

- **Given** every committed workflow
- **When** each `guard` job's declared outputs are compared against the file's `needs.guard.outputs.*` uses
- **Then** no output is unread
- **Test:** `tests/test_workflow_guards.py::test_no_guard_declares_an_output_nobody_reads`
