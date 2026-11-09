# vllm-rocm-thin-prebuilt

## ADDED Requirements

### Requirement: the rocm cell builds as a THIN prebuilt image over AMD's official rocm/vllm base

The vllm rocm cell MUST be a thin image over AMD's official prebuilt serving base
(`FROM docker.io/rocm/vllm:<AMD-tag>`, `prebuilt: true`, `install: []` — zero install steps), so
`engine-build vllm x rocm` no longer compiles the pinned sha or tries to build the `rocm==0.1.0`
placeholder under `--no-build-isolation` (issue #1558).

WHEN `make build-engine ENGINE=vllm ARCH=rocm` runs
THEN the produced `Dockerfile.rocm` is only `FROM docker.io/rocm/vllm:<AMD-tag>` + the llgenie
entrypoint/healthcheck wrap, and the rocm params carry `prebuilt: true` with `install: []`.

#### Scenario: the rocm cell builds from the AMD base with zero install steps

- **Given** the vllm skill's rocm container block with `base: docker.io/rocm/vllm:<AMD-tag>` and `prebuilt: true`
- **When** `make build-engine ENGINE=vllm ARCH=rocm` runs
- **Then** the generated `Dockerfile.rocm` is `FROM docker.io/rocm/vllm:<AMD-tag>` + the entrypoint/healthcheck wrap and `params/vllm.json` rocm has `install: []`, and `make check-engine-params` reports `0 file(s) stale`
- **Test:** `python3 scripts/engine_skills.py params --check` exits 0 and the generated Dockerfile.rocm starts `FROM docker.io/rocm/vllm:`

### Requirement: pushless rocm local verify builds route to the docker driver (no export+load ENOSPC)

A pushless (`--load`) rocm verify build of the ~60+ GiB unpacked AMD base MUST run on the `docker`
driver (flagged via `NO_CACHE_EXPORT`) so the engine-build verify cell does not ENOSPC in the
container driver's export+load (~3x, issue #1915 class, run 42531128064).

WHEN an rocm cell builds on a pushless verify
THEN `engine_image._buildx` selects the `default` docker builder (`no_cache_export` clips the
`--load` cache-export path), and the cell completes without `no space left on device`.

#### Scenario: the pushless rocm verify cell flags the docker driver and goes green

- **Given** `("vllm","rocm")` is in `NO_CACHE_EXPORT` in `scripts/engine_image.py`
- **When** a pushless `engine-build vllm x rocm` verify runs
- **Then** it uses the `default` (docker) builder and completes without ENOSPC
- **Test:** `python3 tests/test_engine_build_workflow.py` green; the verify cell quotes `building with "default" instance using docker driver`
