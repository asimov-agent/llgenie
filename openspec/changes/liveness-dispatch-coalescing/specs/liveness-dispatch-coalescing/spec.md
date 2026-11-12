# Spec Delta — liveness-dispatch-coalescing (#2579)

## ADDED Requirements

### Requirement: multi-cell waves dispatch ONE sweep

When the committed-pin fleet gate reports more than one missing cell, registry-liveness SHALL
dispatch exactly ONE `engine-build` run with `push=true` and no engine/arch inputs (the
producer's documented full-matrix sweep), instead of one run per cell. The `engine-build-push`
concurrency group SHALL see a single queued producer per liveness fire.

#### Scenario: two missing cells dispatch one sweep

- **Given** a registry-liveness run whose gate prints two `[select]` lines (e.g. mlx cpu and
  vllm rocm)
- **When** the dispatch step runs
- **Then** it logs the coalescing decision with the cell count, dispatches one
  `gh workflow run engine-build.yml … -f push=true` with no `-f engine=`/`-f arch=` on that
  call, and dispatches no per-cell run

### Requirement: a single missing cell keeps the per-cell dispatch

When exactly one cell is missing, registry-liveness SHALL dispatch that cell per the [select]
contract (`-f engine="$engine" -f arch="$variant" -f push=true`), keeping the #2567 named-field
binding.

#### Scenario: one missing cell dispatches exactly that cell

- **Given** a gate report with a single `[select]` line
- **When** the dispatch step runs
- **Then** exactly one engine-build dispatch carries that line's engine, variant and push=true

### Requirement: contract validation precedes every dispatch shape

The #2567 positional validation of `[select]` lines SHALL run before either dispatch path; a
line violating the contract SHALL be printed as UNRECOGNIZED and fail the step, and no sweep
or per-cell dispatch shall fire from a malformed report.

#### Scenario: malformed lines dispatch nothing

- **Given** a select.txt line whose first token is not `[select]` or with the wrong token count
- **When** the dispatch step runs
- **Then** the step prints the refusal, exits non-zero, and dispatches nothing

### Requirement: the fleet gate's hard-fail and tracking issues are untouched

The coalescing SHALL NOT change the gate step's `exit "$rc"`, the per-cell tracking-issue
step, or `engine-build.yml` itself.

#### Scenario: gate exit preserved

- **Given** the dispatch step rewritten for coalescing
- **When** the workflow text is checked
- **Then** `exit "$rc"` still ends the gate step and the sweep uses only inputs
  `engine-build.yml` already documents (engine/arch optional, push)
