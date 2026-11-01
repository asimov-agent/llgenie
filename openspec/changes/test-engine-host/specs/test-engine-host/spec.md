# test-engine-host

## ADDED Requirements

### Requirement: make test-engine-host is a parameterized ENGINE/ARCH/MODEL command that serves one engine's smallest model and proves it answers

`make test-engine-host` MUST take `ENGINE=<id> ARCH=<arch> MODEL=<model>` as parameters (the
owner-refined form, issue #1322). `MODEL` selects the LLM model to serve with (already fits host
VRAM and the engine supports it); when omitted, the engine's smallest supported model (the
repository's single smallest-model-per-format table) is served. The engine list and each engine's
max-performance input MUST be read from the committed params (`containers/engines/params/*.json`,
`variants.<arch>.launch`/`env` via `engine_image.resolve`) — never a hard-coded second copy. It
MUST pull the published image (nothing is built locally), assert an llm-local `/v1/chat/completions`
answer, and report the measured tokens/sec a real run produced. Filtering reuses
`nvidia_compute_caps()` / `rocm_gfx_targets()` in `scripts/engine_skills.py` (cpu always). Any
directly-attempted host-supported engine that cannot serve MUST fail (exit non-zero); GPU legs on a
GPU-less host are skipped with a documented reason and never redden.

WHEN the command runs with a supplied MODEL and ARCH
THEN it serves exactly that model on that arch, reads launch/env from the params, asserts llm-local,
and reports a real t/s number.

#### Scenario: a host without a GPU serves only its cpu cells

- **Given** the host has no nvidia CUDA caps and no rocm targets
- **When** `make test-engine-host ENGINE=<id> ARCH=cpu` runs
- **Then** only the cpu variant is attempted, served and answered, and the run exits 0
- **Test:** `tests/test_engine_host.py::test_host_supported_archs_cpu_only`

#### Scenario: a MODEL parameter selects what is served

- **Given** a published image for engine `x` variant `cpu` and a MODEL that fits host VRAM
- **When** `make test-engine-host ENGINE=x ARCH=cpu MODEL=<model>` runs
- **Then** exactly `<model>` is served (threaded unchanged into `serve_published`), llm-local
  answers, and the reported t/s came from the response's own `timings`/`usage` field
- **Test:** `tests/test_engine_host.py::test_model_parameter_selects_what_is_served`

#### Scenario: a transient Hub 503 during the model fetch is retried, not fatal

- **Given** the HuggingFace Hub returns a transient 503 on the smallest-model fetch
- **When** the engine's smallest model is resolved
- **Then** the fetch is retried with backoff and eventually serves (a Hub blip never aborts the run)
- **Test:** `tests/test_engine_host.py::test_smallest_model_retries_transient_503`

#### Scenario: a directly-attempted engine that cannot serve fails loudly

- **Given** a host-arch-supported engine whose image is not published
- **When** `make test-engine-host ENGINE=x` runs
- **Then** the run exits non-zero with a FAIL line; it is never reported as a pass or a silent skip
- **Test:** `tests/test_engine_host.py::test_served_failure_returns_nonzero`

### Requirement: the engine-build workflow's last step runs the same parameterized command as a parallel matrix over the runner's supported cells

The engine-build workflow's LAST step MUST run `make test-engine-host ENGINE=ARCH=MODEL=` as a
matrix over the supported (engine × arch) cells IN PARALLEL (one matrix element per cell), with the
supported set keyed off the arch types the GitHub Actions runner itself supports (checked at runtime
on the runner, never the dev host). A GPU-less runner skips the GPU legs with the same documented
#1240 reason and never reddens; the cpu legs run.

WHEN engine-build pushes an engine x arch image
THEN its last step runs the parameterized host command over that cell, in parallel across cells.

#### Scenario: published row's last matrix step runs the parameterized host command

- **Given** an engine-build workflow publishing row (engine, variant)
- **When** the build+test+push steps complete
- **Then** a final matrix step runs `make test-engine-host ENGINE=<engine> ARCH=<variant> MODEL=<model>`
- **Test:** `tests/test_engine_build_workflow.py::test_the_published_rows_last_matrix_step_runs_the_parameterized_host_command`

### Requirement: check-wiring sees the command as real calling, never a gate weakened

`scripts/engine_host_test.py` MUST be wired to `make test-engine-host` (named by that target's
recipe and the workflow's matrix step), and `make check-wiring` MUST pass. The host-only-wiring
position for host engine serving is REAL calling — the command is the caller, not a roster silence.
Scope exceptions use subset checks (`expected <= set(actual)`), never exact-equality lists.

WHEN `make check-wiring` runs
THEN the host-test script is named by the make target and by CI, and the guard passes without an
exact-list assertion.

#### Scenario: check-wiring passes for the new command

- **Given** `scripts/engine_host_test.py` exists and is named by `test-engine-host` and the workflow
- **When** `make check-wiring` runs
- **Then** it exits 0 and reports the script as wired
- **Test:** `tests/test_wiring.py` (the tree's existing check-wiring fixtures exercise the invented
  layout; the real guard run reports "OK 317 documents")
