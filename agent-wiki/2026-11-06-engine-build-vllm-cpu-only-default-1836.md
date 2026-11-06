# Default vllm build is CPU-only; GPU cells build only on explicit ARCH= (#1836)

**Issue:** #1836 — engine-build: default vllm build = CPU only; cuda/rocm only when ARCH= is
explicit (not the default pipeline).

**Owner directive (2026-11-06):** allow the cpu variant; build the rocm/cuda vllm engine only when
mentioned — it is not part of the default build engine pipeline.

## What changed

`scripts/engine_image.py` `matrix()` gained a `DEFAULT_CPU_ONLY` engine set (`{"vllm"}`). In the
default whole-set sweep (`ARCH=` empty, i.e. `make engine-build-matrix` with `ARCH=""`), an engine
in that set emits only its `cpu` cell; the vllm `cuda`/`rocm` cells are no longer part of the
default pipeline. An explicit `ARCH=cuda` / `ARCH=rocm` still builds exactly that GPU cell (the
existing `arch and key != arch` filter is unchanged, so the explicit path narrows to the requested
variant and is unaffected by the default-cpu-only rule). All other engines' default sweep is
unchanged; `engine-build.yml` dispatch inputs are unchanged.

## Evidence

- **cuda OOM:** run `42176975953`, cell `engine-build-vllm-cuda` (job `127761440511`) — `make
  build-engine ENGINE=vllm ARCH=cuda` → `make: *** [Makefile:1321: build-engine] Killed`, **exit
  code 143**, after ~26.5 min (07:02:02Z→07:28:31Z). Runner/build-resource kill — not an HTTP
  timeout (no `UV_HTTP_TIMEOUT` bump applies).
- **rocm timeout:** run `42159549121`, cell `engine-build-vllm-rocm` (job `127701755286`) — ran
  03:57:11Z→07:55:51Z (~4 h) and was cancelled at the wall.

## Verification

`make -s engine-build-matrix ENGINE="" ARCH=""` (default sweep) now lists vllm as `cpu` only; the
explicit `ARCH=cuda` and `ARCH=rocm` dispatches still list the vllm GPU cells. New unit test
`test_default_vllm_matrix_is_cpu_only_and_explicit_arch_builds_gpu` (in
`tests/test_engine_image_matrix.py`) asserts the default vllm matrix contains `cpu` and excludes
`cuda`/`rocm`, and that explicit `arch=cuda`/`arch=rocm` emit those cells. Engine-matrix suite: 22
passed.

**Vehicle:** #1836. **Openspec:** `openspec/changes/engine-build-vllm-cpu-only-default/`.
