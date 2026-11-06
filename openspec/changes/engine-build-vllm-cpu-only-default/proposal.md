# engine-build-vllm-cpu-only-default

## Why

The default whole-set `engine-build` sweep (`make engine-build-matrix` with `ENGINE=` and `ARCH=`
empty) emits one matrix row per engine x variant from `containers/engines/params/*.json`, so vLLM's
`cuda` and `rocm` cells are built as part of the default pipeline. Neither fits the standard runner:

- **cuda** — run `42176975953`, cell `engine-build-vllm-cuda` (job `127761440511`): `make
  build-engine ENGINE=vllm ARCH=cuda` → `make: *** [Makefile:1321: build-engine] Killed`, **exit
  code 143**, after ~26.5 min (07:02:02Z→07:28:31Z). The 16 GiB runner OOMs on vllm's CUDA
  compile; not an HTTP timeout (no `UV_HTTP_TIMEOUT` bump applies).
- **rocm** — run `42159549121`, cell `engine-build-vllm-rocm` (job `127701755286`): ran
  03:57:11Z→07:55:51Z (~4 h) and was cancelled at the wall.

Owner directive 2026-11-06 (verbatim): *"allow the cpu variant and we have to tell explicitly to
build the rocm/cuda vllm engine accordingly only when mentioned — it's not part of the default build
engine pipeline."* The default vllm build is **CPU only**; a vllm `cuda`/`rocm` cell must not appear
in the default whole-set sweep. The GPU cells stay buildable when `ARCH=cuda` / `ARCH=rocm` is
passed **explicitly**.

## What changes

`scripts/engine_image.py` `matrix()` excludes the vllm `cuda`/`rocm` variants from the default
(empty-`arch`) whole-set sweep; a per-engine default-variant list keeps vllm at `cpu` only when
`arch=""`. Passing `ARCH=cuda` / `ARCH=rocm` still emits the vLLM GPU cell (the existing
`arch and key != arch` filter is unchanged, so the explicit path builds exactly that variant).
`engine-build.yml`'s `workflow_dispatch` inputs are unchanged — `arch=""` is the default CPU-only
sweep, `arch=cuda`/`arch=rocm` the explicit GPU builds.

## Out of scope

- Prebuilt vllm wheels for the repo's target archs (cu130 / gfx1030..gfx942) — separate decision.
- Bounding the `engine-pins` / pr-trigger wait so a stuck image fails loudly — separate
  CI-hardening item.
- vllm's `arch=""` explicit CPU-only default is this change; all other engines keep their current
  default sweep unchanged.
