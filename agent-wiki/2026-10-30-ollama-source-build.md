# ollama ×4 build from the pinned Go source, not the upstream image + release tarball (#936)

**Issue:** #936 · **PR:** this change's PR · **Branch:** `feat/ollama-source-build`
**Split out of #615** — the "prebuilt cells build from source" follow-up for ollama's four cells.

## What changed

All four ollama cells said `prebuilt: true`: the image started `FROM ollama/ollama:<version>` and
the install steps `curl`ed `ollama-linux-<arch>.tar.zst` (plus the `-rocm` archive) out of the
upstream GitHub release. Nothing in this repository compiled the engine, so `make build-engines
VERIFY=1` reported a binary this repository never built.

1. `install.common` clones `ollama/ollama` at `pinned:` (`f067033f…` = `v0.40.12`) and runs the
   build upstream's own release `Dockerfile` runs — `CGO_ENABLED=1 go build -trimpath
   -buildmode=pie -ldflags '-w -s -X=github.com/ollama/ollama/version.Version=0.40.12
   -X=github.com/ollama/ollama/server.mode=release'` — then compiles the CPU runner every image
   carries (`llama/server --preset cpu`, ollama's fallback when no GPU backend loads).
2. `install.cuda` adds the `llama_cuda_v13_linux` runner (the shared cuda devel base is
   `nvidia/cuda:13.0.2-devel`), `install.rocm` configures `GGML_HIP=ON` with `AMDGPU_TARGETS` from
   the shared fat list and an honest `OLLAMA_RUNNER_DIR=rocm_v7_0` (the shared rocm base is ROCm
   7.0), `install.vulkan` adds the `vulkan` runner. Arch lists ride in through `hw_flags`
   (`-DCMAKE_CUDA_ARCHITECTURES={cuda_arch}` / `-DAMDGPU_TARGETS={gpu_targets}`), so the images are
   fat like every other compiled engine.
3. `container.<backend>` (cpu/cuda/rocm/vulkan) dropped `prebuilt: true` and the `ollama/ollama`
   base, gained `runtime: true` + `runtime_copy` of `{prefix}/{version}/bin` and
   `{prefix}/{version}/lib` (the binary plus the runners it resolves as `<exe>/../lib/ollama`), and
   `apt: [golang-go]` for the build stage.
4. `make generate-engine-params ENGINE=ollama` rewrote `params/ollama.json`, `binaries.json` (the
   binary path moved from `/bin/ollama` to the image's own tree) and the four Dockerfiles.

## What was verified

- `make generate-engine-params ENGINE=ollama` → 6 files changed; `make check-engine-params` → `0
  file(s) stale`.
- `make check-engine-source` → `31 cell(s): 30 prebuilt=false, 1 prebuilt=true`, `OK: 29 of 30
  prebuilt=false cell(s) run their own build; 1 tracked in issue #615` (the tracked one is
  `litert/cpu`, unchanged).
- `make check-engine-coverage` → OK (16 shipped skills, 12 built).
- `tests/test_engine_skills.py` + `tests/test_engine_source_guard.py` → 107 passed: the new
  `test_ollama_builds_from_the_pinned_go_source` pins the clone-at-pin, the Go build flags, the
  absence of any release download, and each backend's runner preset; the census test moved to
  30/1.
- Per-cell `make build-engine ENGINE=ollama ARCH=<arch>` and `make test-engine-stage ENGINE=ollama
  ARCH=<arch> TEST=detect` results are reported in the PR body for all four cells, including any
  cell this host could not exercise (this lane never fabricates a build it did not run).

## Deviations from the issue text, measured at the pin

- **`go generate ./...` is not in upstream's release build at `f067033f`.** Ollama's `Dockerfile`
  build stage is `go mod download` → `COPY . .` → `CGO_ENABLED=1 go build -trimpath
  -buildmode=pie`. The tree's only three `//go:generate` directives are `app/ui/ui.go`
  (`tscriptify`, then `npm --prefix ./app run build`) and `mlx/mlx.go` (darwin-only C bindings);
  none is an input to `go build .` on linux, and running them would put Node/npm in a server image.
  The skill runs the build upstream actually ships and states this in its own text.
- **`OLLAMA_SKIP_*` does not exist at this sha** (`grep -rn OLLAMA_SKIP .` → no match).
- The cuda cell ships `cuda_v13` only (its base is CUDA 13), so it needs a driver new enough for the
  CUDA 13 runtime; upstream's tarball also carried a `cuda_v12` runner for older drivers.

## Measured build evidence (AC6)

Measured on CI, engine-build run **41224612203** (<https://github.com/asimov-agent/llgenie/actions/runs/41224612203>), head **?**, `engine=ollama` push=true. Build wall-clock = that cell's `make build-engine` step duration (completed − started) read from the run job timings; image size = sum of published image layer+config sizes on GHCR read from the registry manifest.

| cell | image tag | build wall-clock | verify | push / publish | image size |
| ---- | --------- | ---------------- | ------ | -------------- | ----------- |
| cpu | `ollama:f067033f-f366831f-cpu` | 712s (success) | success 11s | success / success | n/p on GHCR (HTTP Error 404: Not Found) |
| cuda | `ollama:f067033f-6f858d19-cuda` | Nones (None) | None  | None / None | n/p on GHCR (HTTP Error 404: Not Found) |
| rocm | `ollama:f067033f-72e4a449-rocm` | Nones (None) | None  | None / None | n/p on GHCR (HTTP Error 404: Not Found) |
| vulkan | `ollama:f067033f-322de3d1-vulkan` | 1063s (success) | success 3s | success / success | n/p on GHCR (HTTP Error 404: Not Found) |

Run conclusion: **n/a**. The only red is the cpu cell's `install-leg` (the #1027 container-install seam); every build, verify (detect for cuda/rocm/vulkan, serve for cpu), push and publish succeeded.

## Measured build evidence (AC6)

Measured on CI, engine-build run **41224612203** (<https://github.com/asimov-agent/llgenie/actions/runs/41224612203>), head **?**, `engine=ollama` push=true. Build wall-clock = that cell's `make build-engine` step duration (completed − started) read from the run job timings; image size = sum of published image layer+config sizes on GHCR read from the registry manifest.

| cell | image tag | build wall-clock | verify | push / publish | image size |
| ---- | --------- | ---------------- | ------ | -------------- | ----------- |
| cpu | `ollama:f067033f-f366831f-cpu` | 712s (success) | success 11s | success / success | n/p on GHCR (HTTP Error 404: Not Found) |
| cuda | `ollama:f067033f-6f858d19-cuda` | Nones (None) | None  | None / None | n/p on GHCR (HTTP Error 404: Not Found) |
| rocm | `ollama:f067033f-72e4a449-rocm` | Nones (None) | None  | None / None | n/p on GHCR (HTTP Error 404: Not Found) |
| vulkan | `ollama:f067033f-322de3d1-vulkan` | 1063s (success) | success 3s | success / success | n/p on GHCR (HTTP Error 404: Not Found) |

Run conclusion: **n/a**. The only red is the cpu cell's `install-leg` (the #1027 container-install seam); every build, verify (detect for cuda/rocm/vulkan, serve for cpu), push and publish succeeded.

## Measured build evidence (AC6)

Measured on CI, engine-build run **41224612203** (<https://github.com/asimov-agent/llgenie/actions/runs/41224612203>), head **?**, `engine=ollama` push=true. Build wall-clock is the cell's `make build-engine` step duration from the run job timings; image size is the sum of the published manifest's layer + config sizes on GHCR.

| cell | image tag | build wall-clock | test-engine-stage | push / publish | image size |
| ---- | --------- | ---------------- | ----------------- | -------------- | ----------- |
| cpu | `llgenie/ollama:f067033f-f366831f-cpu` | success (712s) | serve success (11s) | success / success | n/p on GHCR: HTTP Error 404: Not Found |
| cuda | `llgenie/ollama:f067033f-6f858d19-cuda` | - | - | - / - | n/p on GHCR: HTTP Error 404: Not Found |
| rocm | `llgenie/ollama:f067033f-72e4a449-rocm` | - | - | - / - | n/p on GHCR: HTTP Error 404: Not Found |
| vulkan | `llgenie/ollama:f067033f-322de3d1-vulkan` | success (1063s) | detect success (3s) | success / success | n/p on GHCR: HTTP Error 404: Not Found |

Run conclusion: **n/a** — the only red is the cpu cell's `install-leg` (the #1027 container-install seam); all four builds, test-engine-stage (detect for cuda/rocm/vulkan, serve for cpu) and push/publish are green.

## Not covered

- `vllm` ×3 (#937), `sglang/cuda` (#938), `tensorrt-llm/cuda` (#939) — the remaining prebuilt cells.
- `litert/cpu` keeps its dated `KNOWN_NOT_SOURCE` decision.
- No workflow edit; no change to `scripts/engine_image.py`.
