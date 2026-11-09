# vLLM cuda cell is a THIN image over vLLM's official CUDA serving base (#2386)

**Issue:** #2386 · **PR:** #2429 · **Branch:** `llgenie-engines-vllm-cuda-wheel`

## What changed

The vLLM `cuda` cell (`make build-engine ENGINE=vllm ARCH=cuda`) stopped source-compiling the
pinned sha and is now a **thin image over vLLM's official prebuilt CUDA serving base**:

```
FROM docker.io/vllm/vllm-openai:v0.33.0
```

plus the llgenie entrypoint/healthcheck wrap — the base image **as-is, trimmed**. `prebuilt: true`
runs **zero install steps** (`install: []`), so there is no `git clone`, no `-r requirements/build/cuda.txt`,
no `tools/build_rust.sh`, no `-e .`, **no wheel-install chain** either. The base (vLLM's official CUDA
serving image) already ships the compiled vllm + CUDA runtime; the served version is its baked vllm,
and `detect` probes it via `from vllm import __version__`. This mirrors the rocm cell treatment
(#1558 / PR #2274: `FROM docker.io/rocm/vllm:<AMD-tag>`, `prebuilt: true`).

`container.cuda` in `skills/engines/vllm/SKILL.md`:

```yaml
cuda:
  base: docker.io/vllm/vllm-openai:v0.33.0
  prebuilt: true          # runs ZERO install steps
  binary: "vllm"
  binary_flags: ["--version"]
```

Supersedes #937/#615's anti-wheel/source-compile direction **for the cuda cell only**. The cpu cell
remains source-compiled (no prebuilt cpu serving image today); rocm is the thin AMD image (#2274).

## What was verified

- `make generate-engine-params ENGINE=vllm` → `containers/engines/params/vllm.json` cuda:
  `base=docker.io/vllm/vllm-openai:v0.33.0`, `prebuilt=true`, `install=[]` (0 steps).
- `Dockerfile.cuda` is only `FROM docker.io/vllm/vllm-openai:v0.33.0` + entrypoint/healthcheck wrap.
- `make check-engine-params` → `0 file(s) stale`; regenerate → `0 file(s) changed` (no drift).
- `make check-docs` green (change->note gate).

## Anything left open

- The published cuda tag must come from a producer run at the PR head; this lane never builds an
  engine image locally.
