# test-engine-host

## ADDED Requirements

### Requirement: make test-engine-host serves each host-arch-supported engine's smallest model and proves it answers

`make test-engine-host` MUST load the engine list from the committed params
(`containers/engines/params/*.json`, the same single source the build matrix uses), filter to the
engines whose arch type the host running it supports, and serve each such engine ONE AT A TIME (a
serial loop, never parallel) against its smallest supported model. It MUST pull the published image
(nothing is built locally) and assert an llm-local `/v1/chat/completions` answer, then report the
measured tokens/sec a real run produced. The per-engine max-performance input (contexts/slots,
kv-quant, offload, flash-attn, moe) MUST be read from the generated params `variants.<arch>.launch`
via `engine_image.resolve` — never a hard-coded second copy. Any directly-attempted host-supported
engine that cannot serve MUST fail the run (exit non-zero); GPU legs on a GPU-less host are skipped
with a documented reason and never redden.

WHEN the command runs on a host whose arch grid is measured (cuda via `nvidia_compute_caps`, rocm
via `rocm_gfx_targets`, cpu always)
THEN it serves one engine at a time over the host-supported subset, reads launch/env from the
params, asserts llm-local, and reports a real t/s number.

#### Scenario: a host without a GPU serves only its cpu engines

- **Given** the host has no nvidia CUDA caps and no rocm targets
- **When** `make test-engine-host` runs
- **Then** only the cpu variants of the committed engines are attempted, each served and answered,
  and the run exits 0
- **Test:** `tests/test_engine_host.py::test_host_supported_archs_cpu_only`

#### Scenario: a served engine answers and reports its measured t/s

- **Given** a published image for engine `x` variant `cpu`
- **When** `make test-engine-host ENGINE=x` runs
- **Then** `engine_image.pull_published` pulled the AS-PUBLISHED tag (never built), a real
  `/v1/chat/completions` returned a non-empty `llm-local` message, and the reported t/s came from
  the response's own `timings`/`usage` field
- **Test:** `tests/test_engine_host.py::test_measure_tps_reads_server_fields`

#### Scenario: a directly-attempted engine that cannot serve fails loudly

- **Given** a host-arch-supported engine whose image is not published
- **When** `make test-engine-host ENGINE=x` runs
- **Then** the run exits non-zero with a FAIL line; it is never reported as a pass or a silent skip
- **Test:** `tests/test_engine_host.py::test_served_failure_returns_nonzero`

### Requirement: the engine-build workflow's last step runs the same command

The engine-build workflow's LAST step MUST invoke `make test-engine-host` on the CI runner for every
engine x arch row it publishes, so a build that publishes an engine that cannot serve proves it on
the runner. A GPU-less runner (no nvidia caps, no rocm) skips the GPU legs with the same documented
#1240 reason the host command already prints, and never reddens them; the cpu legs run.

WHEN engine-build pushes an engine x arch image
THEN its last step runs the exact host command over that engine with its smallest supported model.

#### Scenario: published row's last step runs test-engine-host

- **Given** an engine-build workflow publishing row (engine, variant)
- **When** the build+test+push steps complete
- **Then** a final step named `host-verify-leg` runs `make test-engine-host ENGINE=<engine> ARCH=<variant>`
- **Test:** `tests/test_engine_build_workflow.py` (wiring reads the workflow's run steps)

### Requirement: check-wiring sees the command as real calling, never a gate weakened

`scripts/engine_host_test.py` MUST be wired to `make test-engine-host` (named by that target's
recipe and the workflow's last step), and `make check-wiring` MUST pass. The host-only-wiring
position for host engine serving is REAL calling — the command is the caller, not a roster silence.
Scope exceptions use subset checks (`expected <= set(actual)`), never exact-equality lists, so the
next engine addition does not redden the guard.

WHEN `make check-wiring` runs
THEN the host-test script is named by the make target and by CI, and the guard passes without an
exact-list assertion.

#### Scenario: check-wiring passes for the new command

- **Given** `scripts/engine_host_test.py` exists and is named by `test-engine-host` and the workflow
- **When** `make check-wiring` runs
- **Then** it exits 0 and reports the script as wired
- **Test:** `tests/test_wiring.py` (the tree's existing check-wiring fixtures exercise the invented
  layout; the real guard run reports "OK 316 documents")
