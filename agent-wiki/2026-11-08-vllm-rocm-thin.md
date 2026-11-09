# vLLM rocm cell is a THIN image over AMD's official rocm/vllm base — plus local-verify disk-save routing (#1558)

**Issue:** #1558 · **PR:** #2274 · **Branch:** `fix/1558-rocmm-poetry-bootstrap`

## What changed

Two coupled items stop the vLLM rocm cell from dying or crawling on a shared runner:

1. **Thin prebuilt base (owner decision 2026-11-08; engine code on main via #2429).**
   The rocm cell is `prebuilt: true` over AMD's official
   `docker.io/rocm/vllm:rocm10.1.0_ubuntu24.04_py3.14-pytorch_2.13.0_vllm-0.29.0` — `FROM <AMD>`
   + the llgenie entrypoint/healthcheck wrap, **zero install steps** (`install: []`). No `-e .`
   overlay, no `rocm==0.1.0`/poetry `--no-build-isolation`, no 40~75-min source compile. The AMD
   base ships its baked vllm + ROCm runtime; `detect` probes it via `from vllm import __version__`.
   This is the same pattern as sglang/cuda (#1306) and the cuda cell (#2386/#2429).

2. **Local verify builds route to the `docker` driver** (`scripts/engine_image.py` rocm
   `NO_CACHE_EXPORT` entry, issue #1915 class). The AMD rocm/vllm base is ~31.3 GiB compressed /
   ~60+ GiB unpacked (its 22.8 GiB pytorch/ROCm layer). On the docker-container buildx driver,
   a pushless (`--load`) verify run exports the whole image as a tar and unpacks it into dockerd
   ON TOP of the builder store (~3x), which hit `no space left on device` with 106 GiB free
   (run `42531128064`) even though the BUILD succeeded and the same image PUSHES fine.
   With this entry the pushless verify cell flags `no_cache_export` → `_buildx` picks the
   `default` docker builder, which builds straight into the daemon (no export+load tar).
   A `push`/`force` build is unaffected.

## What was verified

- `Dockerfile.rocm` is `FROM docker.io/rocm/vllm:<AMD-tag>` + entrypoint/healthcheck wrap;
  `params/vllm.json` rocm has `prebuilt: true`, `install: []`, `base: docker.io/rocm/vllm:…0.29.0`.
- `make check-engine-params` → `0 file(s) stale`; `check-engine-source` → OK.
- Verify cell `42660443660` @ `5b9aa1f8` — `make build-engine ENGINE=vllm ARCH=rocm` +
  `test-engine-stage TEST=detect` both success on the docker driver (no ENOSPC).
- Engine suite `tests/test_engine_skills.py` + `tests/test_engine_image_matrix.py` +
  `tests/test_engine_source_guard.py` + `tests/test_ci_variant_matrix.py` → green at head.

## Anything left open

- AC-3 (`push=true` publish of the rocm tag) is the post-merge producer sweep, owned by #2290.
- The published tag `3a4d82f5-16c7ff10-rocm` resolves in GHCR (user-published).
