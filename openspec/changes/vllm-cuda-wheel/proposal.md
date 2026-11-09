name: vllm-cuda-wheel
about: cuda cell is a thin image over vLLM's official CUDA serving base instead of source-compiling the pin
status: active
---

# `engines(vllm)`: cuda cell is a THIN image over vLLM's official CUDA serving base (issue #2386)

## Proposal

The vLLM `cuda` cell (`make build-engine ENGINE=vllm ARCH=cuda`) today source-compiles the pinned
sha of `vllm-project/vllm` inside the shared CUDA base image: `git clone`, `uv pip install -r
requirements/build/cuda.txt`, `tools/build_rust.sh` (a Rust toolchain bootstrap) and `-e .` with
`VLLM_TARGET_DEVICE=cuda`. That path is slow, red-prone (issue #1694 hit the 240-minute timeout on
the sibling rocm cell; issue #1832 reddened the cuda cell) and depends on a Rust toolchain the base
does not ship.

This change makes the cuda cell a **thin image over vLLM's official prebuilt CUDA serving base**
instead, for the **cuda cell only**: `container.cuda` declares `prebuilt: true` with
`base: docker.io/vllm/vllm-openai:v0.33.0`, so the generated `Dockerfile.cuda` is only
`FROM docker.io/vllm/vllm-openai:v0.33.0` plus the llgenie entrypoint/healthcheck wrap — **zero
install steps** (`install: []`). The base (vLLM's official CUDA serving image) already ships the
compiled vllm + CUDA runtime; the served version is its baked vllm and `detect` probes it via
`from vllm import __version__`. This mirrors the rocm cell treatment (#1558 / PR #2274:
`FROM docker.io/rocm/vllm:<AMD-tag>`, `prebuilt: true`).

Supersedes #937/#615's anti-wheel/source-compile direction **for the cuda cell only**, and
supersedes the interim wheel-install plan (#2386's earlier "curl + pip install the wheel" form) in
favour of pulling the official prebuilt serving image (no install chain at all). ROCm is thin and
prebuilt too; CPU remains source-compiled (no prebuilt cpu serving image today).

## Motivation

A prebuilt, hash-fixed upstream serving image removes the clone, requirement-file install, Rust
bootstrap, in-place build **and any install chain**. It cuts the cuda cell from a multi-hour,
red-prone compile to a `FROM` + wrap that finishes in minutes, byte-identical and reproducible.
`detect` and the serve contract are unchanged (the base runs `vllm serve … --host 0.0.0.0
--port 11434 --served-model-name llm-local`, `GET /health`).

## Change

1. `skills/engines/vllm/SKILL.md`: `container.cuda` → `base: docker.io/vllm/vllm-openai:v0.33.0` +
   `prebuilt: true` + `binary: "vllm"`; `install.cuda` cleared (0 steps). `container.rocm` thin
   (#2274); `install.cpu` unchanged (source-compiled).
2. `make generate-engine-params ENGINE=vllm`; commit the regenerated `params/vllm.json` and
   `containers/engines/dockerfiles/vllm/Dockerfile.cuda` (now thin `FROM vllm/vllm-openai:v0.33.0`).
3. `scripts/engine_source_guard.py`: `("vllm", "cuda")` in `KNOWN_NOT_SOURCE` — the cell is a thin
   image pull, not a source build — so `check-engine-source` stays green.
4. `tests/test_engine_skills.py`: hermetic test asserting the cuda cell is `prebuilt`/thin with no
   source step and no install chain; a regression back to `-e .`/`build_rust.sh`/wheel reds.
5. `agent-wiki/2026-11-09-vllm-cuda-wheel.md` + `docs/changes.d/…` + regenerated `CHANGES.md`.

## Impact

- `skills/engines/vllm/SKILL.md`, `containers/engines/params/vllm.json`,
  `containers/engines/dockerfiles/vllm/Dockerfile.cuda`.
- `scripts/engine_source_guard.py` (census: vllm/cuda becomes a tracked known-not-source cell).
- `tests/test_engine_skills.py`, `agent-wiki/`, `docs/changes.d/`, `CHANGES.md`.

## Not covered

- CPU vLLM variant (stays source-compiled at the pin; no prebuilt cpu serving image today).
  Other engines unchanged.
