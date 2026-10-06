# llgenie pulls engine images from the published registry without make

## Why

`llgenie` is run straight from `~/bin`. Picking an engine that `make install` did not pre-pull
(Strata, Ollama, vLLM, ...) failed with:

```
[install] FAIL strata/cuda: not published in (no LLGENIE_REGISTRY)
[llgenie] could not install the strata image (cuda); check LLGENIE_REGISTRY / docker ...
```

The image was on GHCR. The default registry `ghcr.io/asimov-agent` was set only in the Makefile
(`export LLGENIE_REGISTRY ?= ...`), and `scripts/engine_image.py` fell back to an empty string, so
only runs through `make` knew where to pull from. Every test runs through make, so CI never saw it.

A second defect showed on the same host run, once the image was pulled: Strata's setup finished,
then the server stopped at once:

```
server.py: error: unrecognized arguments: --model-alias llm-local
```

Strata's `serve/server.py` has no alias flag. Model aliases come from the config's `aliases` list
(Strata #297). CI only ran the image's version check (no GPU), so the launch line was never run.

A third defect showed when the real engine started on the RTX 4090 laptop (i9-13980HX, AVX2,
no AVX-512): `strata --serve` died with SIGILL. gdb: `ggml_cpu_init` executes
`vmovdqa32 ..., %zmm0`. The image compiles Strata with ggml's default `-march=native`, so on an
AVX-512 CI runner ggml's CPU code is AVX-512, and `ggml_cpu_init` runs at every start before
Strata's runtime kernel dispatch. Setup also recompiled the engine at every container start (the
image had no `engine/BUILD.json`), which on this CPU still crashed, the same way. Strata's own
release build uses `STRATA_PORTABLE=ON` (ggml pinned to AVX2; Strata's AVX-512 kernels stay
runtime-dispatched).

## What Changes

- `scripts/engine_image.py`: `DEFAULT_REGISTRY = "ghcr.io/asimov-agent"`; `REGISTRY` falls back to
  it. `LLGENIE_REGISTRY` still overrides it (a fork's GHCR), and `LLGENIE_REGISTRY=` (empty) still
  means local images only.
- Strata launch: adds `llm-local` to the config's `aliases` (kept if already there) and starts
  `serve/server.py --config <cfg> --port --host` with no unknown flag; `alias_mode: config`.
- Strata image build: `-DSTRATA_PORTABLE=ON` (cuda and rocm), and `engine/BUILD.json` written the
  way setup.py's `build_engine` / `build_engine_hip` write it, so setup reuses the image's engine.
- Tests: the default without make (hermetic, `make test-unit`), and a live first-use pull with no
  `LLGENIE_REGISTRY` in the environment (`make test-install-published`, which has the docker socket).

## Impact

`scripts/engine_image.py`, `skills/engines/strata/SKILL.md` + regenerated
`containers/engines/params/strata.json`, `tests/test_engine_skills.py`,
`tests/test_install_published.py`, `tests/test_strata_download.py`, `tests/test_engine_version.py`.

Issue: #110.
