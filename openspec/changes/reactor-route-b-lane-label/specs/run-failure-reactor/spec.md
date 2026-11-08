# reactor-route-b-lane-label

## ADDED Requirements

### Requirement: a pipeline/workflow failure carries the ci-pipelines lane's label

The run-failure reactor MUST label a Route-B issue it files (a failed run with no pushable PR) with
the OWNING LANE's label, so a failure is routed to the lane that owns the fix. A pipeline/gate/bot/
script workflow — `ci-verdict`, `ci-requeue`, `rebase-bot`, `main-ruleset`, … — MUST carry the
ci-pipelines lane's label (`agent:ci-pipelines-maintainer`), NOT the product implementer's
`agent:implement`.

WHEN the reactor files a Route-B issue for a failing pipeline/gate/bot workflow
THEN the issue carries `agent:ci-pipelines-maintainer` and does not carry `agent:implement`

#### Scenario: a ci-verdict failure routes to the ci-pipelines lane
- **Given** a completed failed `ci-verdict — holds a finished CI run to its published scope
  decision, and says "no verdict" out loud` run on main with no pushable PR
- **When** the reactor routes it (Route B)
- **Then** it files exactly one issue whose `--label` is `agent:ci-pipelines-maintainer` and not
  `agent:implement`
- **Test:** `tests/test_run_failure_reactor.py::test_a_red_pipeline_gate_run_files_ci_pipelines_label`

### Requirement: a product workflow still routes to the implementer

A failure of a workflow that runs the PRODUCT's own gates (`CI` / `pipeline`) MUST route to the
implementer's `agent:implement` label exactly as it always has — a product-code failure is the one
case for which the existing behaviour is preserved.

WHEN the reactor files a Route-B issue for a failing product workflow (`CI` or `pipeline`)
THEN the issue carries `agent:implement`

#### Scenario: a product CI failure keeps the implementer label
- **Given** a completed failed `CI` run on main with no pushable PR
- **When** the reactor routes it (Route B)
- **Then** it files one issue whose `--label` is `agent:implement`
- **Test:** `tests/test_run_failure_reactor.py::test_a_red_main_run_with_no_pr_files_one_issue`

### Requirement: the issue body names the owning lane and the failure class

The filed issue body MUST name the owning lane and the failure class, so a reader sees the routing
without re-deriving it. When the workflow is classified, the body names its lane; when it is not
classified, the body names the failure class instead and the issue carries no implementation label.

WHEN the reactor files a Route-B issue
THEN the body carries `**owned by lane:**` and `**failure class:**`

#### Scenario: a classified issue names its lane
- **Given** a failing pipeline-gate run routed to the ci-pipelines lane
- **When** the reactor files the issue
- **Then** the body carries `**owned by lane:** \`llgenie-ci-pipelines-maintainer\``
- **Test:** `tests/test_run_failure_reactor.py::test_a_red_pipeline_gate_run_files_ci_pipelines_label`

### Requirement: an unclassified workflow is filed with no implementation label and names the class

When the failing workflow cannot be classified confidently, the reactor MUST file the issue with NO
implementation label (never defaulting to the product implementer) and name the failure class in the
body instead.

WHEN the reactor files a Route-B issue for a workflow `classify_workflow` cannot classify
THEN the issue carries no `--label` and its body names the failure class

#### Scenario: an unknown workflow files without an implementation label
- **Given** a completed failed run of `some-future-workflow` with no pushable PR
- **When** the reactor routes it (Route B)
- **Then** it files one issue with no `--label`, whose body carries
  `**failure class:** \`some-future-workflow/run tests\``
- **Test:** `tests/test_run_failure_reactor.py::test_an_unclassified_workflow_files_with_no_implementation_label`

### Requirement: an engine workflow is filed with no implementation label and its lane named

The engine/serving lane (`llgenie-engine-improver`) owns engine build/serve work but has no `agent:*`
queue label on this repository. An engine-workflow failure MUST file the issue with no implementation
label and name the engine lane in the body — never the product implementer.

WHEN the reactor files a Route-B issue for a failing engine workflow (`engine-bump`, `engine-build`, …)
THEN the issue carries no `--label` and its body names `llgenie-engine-improver`

#### Scenario: an engine-bump failure names the engine lane
- **Given** a completed failed `engine-bump — bumps pinned engines` run with no pushable PR
- **When** the reactor routes it (Route B)
- **Then** it files one issue with no `--label`, whose body carries
  `**owned by lane:** \`llgenie-engine-improver\``
- **Test:** `tests/test_run_failure_reactor.py::test_an_engine_workflow_files_with_no_implementation_label`

### Requirement: the dedupe key is class-level, not run-scoped

The dedupe marker MUST be class-level — `WORKFLOW/STEP` (the failing step, not the run sha) — so N
runs of one broken gate (different shas, same failing step) collapse into ONE issue instead of one
per run.

WHEN the reactor builds the dedupe marker for a failing run
THEN it is `<!-- run-fixer: WORKFLOW/STEP -->` with no head sha, and a second run of the same
workflow that fails the same step files nothing

#### Scenario: a repeated broken gate files nothing
- **Given** an OPEN issue already carrying `<!-- run-fixer: CI/run tests -->` and a later failed
  `CI` run (a DIFFERENT sha) failing the same `run tests` step
- **When** the reactor routes the later run
- **Then** it prints `already filed` and files nothing
- **Test:** `tests/test_run_failure_reactor.py::test_a_repeated_broken_gate_files_nothing`

## MODIFIED Requirements

### Requirement: the reactor's entrypoint still routes through `make run-failure-reactor`

The workflow still invokes the reactor through the make target (`make run-failure-reactor`) and the
`issue create`/`issue`/`api` verbs are the only writes (it files, never pushes/merges). The route
decision stays in code, never in a job `if:`.

WHEN the reactor files a Route-B issue
THEN the only gh writes are `issue create` and `issue list` reads (the reactor never pushes, commits
or merges)

#### Scenario: the file-issue path writes only an issue
- **Given** a failed run with no pushable PR routed to Route B
- **When** the reactor runs end-to-end
- **Then** every `gh` call is an `api`/`run`/`issue` verb and exactly one `issue create` happens
- **Test:** `tests/test_run_failure_reactor.py::test_the_file_path_writes_only_an_issue`
