# ollama ×4 build from the pinned Go source, not the upstream image + release tarball (#936)

## Why

All four ollama cells (`cpu`, `cuda`, `rocm`, `vulkan`) say `prebuilt: true`: each image starts
`FROM ollama/ollama:<version>` and its install steps `curl` `ollama-linux-<arch>.tar.zst` (plus the
`-rocm` archive) from the upstream GitHub release and unpack it. Nothing in this repository
compiles the engine, so `make build-engines VERIFY=1` reports a binary this repository never built,
and a pinned-sha regression (a Go module bump, a llama.cpp runner change in ollama's own tree) is
invisible to the whole matrix — the image just re-downloads whatever upstream shipped for that tag.

Ollama's own release build is a **Go build of the repo at the tag** plus a **CMake build of the
llama.cpp runner(s) vendored in that same tree** (`llama/server` presets, `LLAMA_CPP_VERSION`).
Both are reproducible here from the pin, with the toolchains the shared devel bases already carry.

## What changes

1. `skills/engines/ollama/SKILL.md`: `install.common` clones `ollama/ollama` at `pinned:`
   (`f067033f…`, the tag `v0.40.12`) and runs upstream's own Go build —
   `CGO_ENABLED=1 go build -trimpath -buildmode=pie -ldflags '-w -s -X=…/version.Version=…
   -X=…/server.mode=release'` — exactly the settings ollama's release `Dockerfile` build stage
   uses, plus the CPU runner (every cell ships one, because ollama falls back to it when no GPU
   backend loads). Each GPU backend adds its own runner from the in-repo `llama/server` CMake
   presets: `llama_cuda_v13_linux` (cuda, on the CUDA-13 devel base), the `rocm_v7_2_base` cache
   variables with `AMDGPU_TARGETS` from the shared fat list and a truthful `rocm_v7_0` runner dir
   (the shared rocm base is ROCm 7.0), and `vulkan`. Arch lists come from the shared
   `FAT_CUDA_ARCHS` / `FAT_GPU_TARGETS` through `hw_flags`, so the images are fat like every other
   compiled engine.
2. `container.<backend>` for all four: drop `prebuilt: true` and the `ollama/ollama` base; build on
   the shared devel base for that backend (`llgenie/base-<backend>`) and ship only
   `{prefix}/{version}/bin` + `{prefix}/{version}/lib` onto the slim runtime base
   (`runtime: true`, `runtime_copy: […]`). `apt: [golang-go]` supplies Go in the build stage;
   ollama's `go.mod` requires Go 1.26.10, which the 1.22 toolchain fetches through Go's own
   `GOTOOLCHAIN=auto` (the same mechanism upstream relies on).
3. `make generate-engine-params ENGINE=ollama`; commit the regenerated params + the four
   Dockerfiles.
4. Per cell: `make build-engine ENGINE=ollama ARCH=<arch>` then
   `make test-engine-stage ENGINE=ollama ARCH=<arch> TEST=detect` (cpu also serves a model and
   answers on `/v1/chat/completions`).

## Deviation from the issue text, measured at the pin

- **`go generate ./...` is not part of upstream's release build at `f067033f`.** Ollama's
  `Dockerfile` build stage is `go mod download` → `COPY . .` → `CGO_ENABLED=1 go build -trimpath
  -buildmode=pie`. The tree's only three `//go:generate` directives are `app/ui/ui.go`
  (`tscriptify`, then `npm --prefix ./app run build`) and `mlx/mlx.go` (C bindings, a darwin-only
  package); none is an input to `go build .` on linux, and running them would add a Node/npm
  toolchain to a server image. The skill runs the build upstream actually ships and says so in its
  own text.
- **`OLLAMA_SKIP_*` does not exist at this sha** (`grep -rn OLLAMA_SKIP .` → no match), so the
  settings carried over are the ones that do: `CGO_ENABLED=1`, the `-ldflags` version/mode pair,
  `-trimpath`, `-buildmode=pie`.
- The cuda cell ships `cuda_v13` only (its base is `nvidia/cuda:13.0.2-devel`), so that image needs
  an NVIDIA driver new enough for the CUDA 13 runtime; upstream's tarball carried both `cuda_v12`
  and `cuda_v13` runners. Recorded in the skill.

## Impact

- `skills/engines/ollama/SKILL.md`, `containers/engines/params/ollama.json`,
  `containers/engines/dockerfiles/ollama/Dockerfile.{cpu,cuda,rocm,vulkan}`.
- `tests/test_engine_source_guard.py` (census 30 source / 1 prebuilt on this branch),
  `tests/test_engine_skills.py` (the ollama tarball test becomes a source-build test; the
  official-upstream-image test drops its ollama rows).
- `README.md`, `docs/ENGINES.md`, `agent-wiki/2026-10-30-ollama-source-build.md`, `CHANGES.md`.

## Not covered

- `vllm` (×3, #937), `sglang/cuda` (#938) and `tensorrt-llm/cuda` (#939) — the other prebuilt cells,
  each on its own branch/PR.
- `litert/cpu`, which keeps its dated `KNOWN_NOT_SOURCE` decision.
- Any workflow edit, and any change to `scripts/engine_image.py` beyond what the generated params
  need.
- Shipping both `cuda_v12` and `cuda_v13` runners (it would need a CUDA-12 toolkit in the cuda
  build stage) — named as follow-up work in the PR's `Not covered`.
