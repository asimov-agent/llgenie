# timeout-maintenance-step-jobs

## ADDED Requirements

### Requirement: every maintenance step job declares a maximum runtime

Every non-`uses` (step-running) job in the three scheduled engine/registry maintenance workflows —
`.github/workflows/engine-bump.yml`, `.github/workflows/engine-bump-rebase.yml` and
`.github/workflows/registry-sync.yml` — MUST declare a `timeout-minutes` in the `5..300` hang-ceiling
band, so a hung step surfaces as a loud `timeout` instead of silently inheriting GitHub's 360-minute
default. A `uses:` caller cannot declare a ceiling at all (GitHub refuses the file), so the rule is
scoped to step jobs.

The four previously-unbounded step jobs get wide-but-bounded ceilings: `engine-bump.yml` `plan`
(git ls-remote + plan) `30`; `engine-bump.yml` `bump` (pin + derive + the live TensorFold archive
proof) `120`; `engine-bump-rebase.yml` `rebase` (forward-merge every open engine-bump PR) `30`;
`registry-sync.yml` `sync` (sync + render + `make test-unit`) `120`. Each is a hang detector, not a
budget.

Capacity only: the change MUST NOT weaken `tests/test_engine_build_timeouts.py` to a narrower job
list, and it MUST NOT alter any step, gate or secret.

WHEN the maintenance workflows run a step job
THEN it carries a `timeout-minutes` in `5..300`, a dropped or absent bound reds the guard, and the
engine-build/pipeline timeouts guards are unchanged.

#### Scenario: the four step jobs carry wide-but-bounded ceilings

- **Given** the three maintenance workflows
- **When** the `plan`/`bump`/`rebase`/`sync` step jobs are read
- **Then** each carries a `timeout-minutes` in the `5..300` ceiling band (`plan`/`rebase` 30, `bump`/`sync` 120)
- **Test:** `tests/test_maintenance_workflow_timeouts.py::test_every_maintenance_step_job_declares_a_timeout`

#### Scenario: every job in the maintenance workflows is bounded, not just the four named

- **Given** the three maintenance workflows
- **When** every non-`uses` job is read
- **Then** all of them — the `guard` jobs and the four step jobs — declare a `timeout-minutes` in range, so a newly added unbounded job reds the guard too
- **Test:** `tests/test_maintenance_workflow_timeouts.py::test_every_maintenance_job_declares_a_timeout`

#### Scenario: a dropped `timeout-minutes` reds the guard (the negative control)

- **Given** a maintenance workflow whose `plan`, `bump`, `rebase` or `sync` job lacks `timeout-minutes`
- **When** the negative-control test runs
- **Then** it fails, naming the workflow and job (guard-proven red on the planted-missing tree, green on the fixed tree)
- **Test:** `tests/test_maintenance_workflow_timeouts.py::test_every_maintenance_step_job_declares_a_timeout` (red on planted-missing, green restored)

#### Scenario: the build and pipeline timeouts guards are not weakened

- **Given** the existing `tests/test_engine_build_timeouts.py` and `tests/test_pipeline_timeouts.py` guards
- **When** this change lands
- **Then** their job lists are unchanged and both still pass
- **Test:** `tests/test_engine_build_timeouts.py` + `tests/test_pipeline_timeouts.py` (unchanged, both green)

## MODIFIED Requirements

### Requirement: the maintenance workflows are covered by a timeout-bounds gate (was: unguarded)

The timeout-bounds net previously pinned only the engine-build workflows
(`ENGINE_BUILD_WORKFLOWS`) and `ci.yml`/`pipeline.yml` (`test_pipeline_timeouts.WORKFLOWS`). The new
guard extends the #1865 family to the maintenance workflows so the #1865 blanket covers them.

WHEN the guard set is extended to add the three maintenance workflows
THEN the maintenance step jobs are bound and the guard reads green, and the existing guards are untouched.
