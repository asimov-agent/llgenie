# Engines: build, test, publish

One inference server per engine, each built, tested and published as a container image from a

generated Dockerfile. `README.md` shows how to use them; `docs/ARCHITECTURE.md` maps the code.

The sections below cover the llama.cpp build rule, tree and backend selection, the install
and verification targets, the CI matrix, the engine skills, on-demand builds and the container
images.

[Tree selection](#tree-selection--card-ram-only-no-model-quant-inspection) · [Backend selection](#backend-selection-hardware) ·

[Install targets](#install-targets) · [Env seams](#env-seams-citest) · [CI matrix](#ci-matrix-githubworkflowsciyml) ·

[Engine skills](#engine-skills--one-per-inference-server-issue-98) ·

[Build on demand](#build-every-engine-at-its-pin-on-demand-engine-buildyml-issue-614) ·

[Container images](#engine-container-images-one-per-engine-x-hardware-arch)

## Which llama.cpp build is used (card-size rule, issue #84)

`make install` picks the llama.cpp **tree** (upstream or Prism) and the **backend** from the
hardware and installs the matching **engine image** (`llgenie/llama-cpp` or
`llgenie/llama-cpp-prism`, `:cpu|cuda|rocm|vulkan`): pulled from GHCR when published, built
from its generated Dockerfile otherwise. `~/bin/llama-server` is a shim that runs the stock llama.cpp image and `~/bin/prism-server`
the Prism image (llgenie picks by card tree);
nothing is compiled on the host (only macOS Metal builds natively, see below).

### Tree selection — card RAM only (no model quant inspection)
Card RAM means the GPU's VRAM when an NVIDIA card is present (via `nvidia-smi`),
otherwise the system RAM. `LLGENIE_RAM_BYTES` is a test/CI seam, not a user knob.

| Card RAM | Tree to build | Why |
|---|---|---|
| 8 GB  | **Prism** | only low-bit PTQ1_0 fits; stock can't load it |
| 12 GB | **Prism** | PTQ1_0 fits; stock can't load it |
| 16 GB | **Prism** | PQ2_0/PTQ1_0 fit; stock can't load them |
| 24 GB | **Prism** | Q4_K fits; Prism runs low-bit AND standard quants |
| 48 GB | **upstream** | Q8_0 fits; stock handles it |
| 64 GB | **upstream** | Q8_0/F16 fits; stock handles it |

The threshold is inclusive on the low side: **card_RAM <= 24 GB -> Prism, > 24 GB -> upstream**
(single constant `PRISM_THRESHOLD_GB = 24` in `scripts/detect_server.py`).

Prism (PrismML-Eng/llama.cpp, branch `prism`) is a **superset** of stock upstream:
it loads every standard quant PLUS the low-bit PTQ1_0/PQ2_0/TQ1_0/TQ2_0 that only it supports.

### Backend selection (hardware)
CUDA (nvidia-smi lists a GPU; containers get the host driver through the
nvidia-container-toolkit CDI device, `sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml`)
· ROCm (`/dev/kfd`) · Vulkan · CPU (fallback) · Metal (macOS, native).

### Install targets
```
make install                              # pull THIS host's tested images (llama.cpp + Prism) + start scripts + version test
make install ENGINES=all                  # every engine for this backend (otherwise llgenie pulls one on first use)
make install ENGINES=vllm ARCH=cuda       # some engines / a forced backend
make install BUILD=1                      # build an image that is not published (default: pull only)
make test-built-engine                    # every ~/bin/llgenie-engine-* prints its engine version
make check-engine-launchers               # CI: a launcher whose tag is not what the committed params compute FAILS
make engine-launchers-report              # the same comparison, printed per engine (launcher tag vs expected)
make ci-wait-engine-images ARCH=cpu       # CI gate: wait until every image `make install` pulls is published (issue #169);
                                          # a producer cell still QUEUED is waited on up to 75 min and reported as BLOCKED,
                                          # a producer that concluded is reported as NOT FOUND (issue #893)
make install-prism-metal     # macOS only: native Metal build (Metal cannot run in a container)
make install-upstream-metal  # macOS only
make install-prism-cpu       # Linux: the Prism llama.cpp engine image (CPU) + start scripts + version test
make install-prism-cuda      # Linux: the same for CUDA (host driver via nvidia-container-toolkit CDI)
make install-upstream-cpu    # Linux: the upstream llama.cpp engine image (CPU)
make install-upstream-cuda   # Linux: the same for CUDA
make uninstall               # removes the launcher, llgenie.py, every llgenie-engine-* start script and the
                             # llama-server / prism-server shims; stops llgenie engine containers (PURGE_IMAGES=1: images too)
# native builds only (macOS Metal / CI server-variants-mac); on Linux use make run-engine
make serve-variant TREE=prism BACKEND=metal          # serve the built binary on a free port
make serve-variant TREE=prism BACKEND=metal PORT=18080
make test-serve-variant TREE=prism BACKEND=metal     # "hi", then stop that server
make stop-serve-variant TREE=prism BACKEND=metal     # stop only the server make started
```

### Launcher freshness — what `check-engine-launchers` does and does not prove

`~/bin/llgenie-engine-<engine>` is generated by `make engine-launchers` and embeds a
content-addressed tag, `<pin[:8]>-<params_hash8>-<variant>`. `make check-engine-launchers`
recomputes that tag from the **committed params using the launcher writer itself**
(`install_engine_launchers.install_plan`, not a second copy of the formula) and compares it with
the `IMAGE=` line of the launcher that is actually installed. A launcher naming another tag is a
**failure**: it would run an older pinned engine and report `--version` happily, or a fresh install
would fail on a tag nobody pushed, with the error pointing at the registry instead of the pin drift
(issue #842). A host with no launcher is informational — that is CI's normal state. `CHECK_REGISTRY=1`
additionally fails a computed tag that resolves no manifest; the default run touches no network and
starts no container.

The tag hashes FOUR inputs, not just the params: the variant's params, its committed Dockerfile,
`containers/engines/entrypoint.sh` and `scripts/engine_runner.py`. A checkout that differs in any
of them recomputes every tag, so run the check against the tree you intend to install from — on a
branch that edits the runner, every launcher will read as stale by design.

It does **not** prove the image runs, that it serves a model, or that a published tag exists —
`make test-built-engine` and the engine-image CI matrix answer those. It also does not publish or
rebuild anything: a stale launcher is fixed by `make engine-launchers ENGINES=<id>`, which pulls.

`make serve-variant` does not rebuild and does not stop a llama-server that is
already running. It binds `127.0.0.1` on `PORT`, or on a free port when `PORT`
is omitted, and it will not bind a port that is already taken.
`--n-gpu-layers` is not passed, so `llama-server` keeps its default and takes
GPU or CPU, whichever it can. The model defaults to the
cached Qwen 0.5B health file under `~/models/Qwen/8GB` and is downloaded only
when that file is missing.

`make test-serve-variant` posts `"hi"` and then stops the process that target
started. `make stop-serve-variant` stops that same recorded pid. Neither one
signals a llama-server that was not started by this Makefile.

### Env seams (CI/test)
- `LLGENIE_BACKEND` = metal | cuda | cpu (| rocm | vulkan for engine skills)  (override hardware detection)
- `LLGENIE_CUDA_ARCH` / `LLGENIE_CUDA_VERSION` / `LLGENIE_GPU_TARGETS` / `BUILD_JOBS` (engine-skill hardware params)
- `LLGENIE_RAM_BYTES` = card RAM in bytes (test/CI seam)
- `LLAMA_SERVER_TREE` = prism | upstream (force the tree, independent of card RAM)
- `LLGENIE_REGISTRY` = registry to pull/push engine images (default `ghcr.io/asimov-agent`)
- `LLGENIE_NO_GPU=1` = start GPU images without GPU devices (CPU fallback; used by CI)
- `LLGENIE_MODELS_DIR` = models dir the start scripts mount (default `~/models`)
- `LLGENIE_QUANT_CATALOG` = path to the HF class table the pick reads (default
  `data/trending-quant-catalog.json`; `0` disables it and always resolves live — a test seam)

### CI matrix (`.github/workflows/ci.yml`)
- **Linux variants run as container images** from their own base images (`engine-image` jobs, see
  "Engine container images" below): upstream llama.cpp `FROM ghcr.io/ggml-org/llama.cpp:server[-cuda]`,
  Prism compiled on the shared toolchain base (Prism cuda/rocm are disabled until #103, so
  cuda/rocm hosts run `prism-server` from the Prism cpu image). Every image has a
  **test stage on the OpenAI API that AI harnesses use**. cpu images serve the 0.5B model and must
  answer `GET /v1/models` (lists `llm-local`) and `POST /v1/chat/completions` on the published port
  (`make test-engine`). GPU images (cuda/rocm/vulkan) print their engine version in the build job
  (`make test-engine-image`); after publishing, the second matrix `engine-published-test` starts
  every image, GPU ones too (without GPU devices, CPU fallback), and chats "hi" with it.
- `server-variants-mac` (**macos-14**, Apple Silicon), four jobs:
  `prism+cpu` beside `prism+metal`, and stock `upstream+cpu` beside
  `upstream+metal`. Metal is Apple-only and cannot run in a container, so these
  build natively and answer the same 0.5B `"hi"` check.
- **Triggers + superseding runs.** `ci.yml` runs on a `pull_request` targeting `main` and on a
  `push` to `main` (a bare feature-branch push runs nothing; a fork PR runs in the fork). It
  declares one `concurrency` group, `${{ github.workflow }}-${{ github.ref }}`, with
  `cancel-in-progress: ${{ github.event_name == 'pull_request' }}` (issue #288): a push to a PR
  **cancels the run started by the push before it** — one PR supersedes its own predecessor, two
  different PRs never cancel each other — while a `push` to `main` is never cancelled (a main run
  mid-publish to GHCR must finish). The bot workflows are deliberately the opposite
  (`cancel-in-progress: false`): a repair or rebase may only be superseded by its own schedule slot,
  never killed mid-agent. `tests/test_ci_concurrency.py` evaluates the expression for both event
  names and fails on any workflow that runs on a pull request with no group, or on an unconditional
  `cancel-in-progress: true`.

## Engine skills — one per inference server (issue #98)

Every inference server in the
[trending-local-llms](https://github.com/andyholst/trending-local-llms) engine registry
has one agent skill: `skills/engines/<id>/SKILL.md`. The skill is the single source
of truth for how to detect, install and launch that engine **on this hardware**.
`scripts/engine_skills.py` runs it and contains no engine-specific code.
On Linux the skills are rendered into the committed per-arch params + Dockerfiles
(`make generate-engine-params`, below); only the native macOS Metal build still reads a skill
at build time (`build_llama_server.sh` takes repo, branch, dirs and cmake flags from
`engine_skills.py build-env`).

```
make engine-hardware                 # detected: backend, compute cap -> CUDA arch, CUDA major, ROCm gfx, cores
make engine-list                     # all 16 skills: servable mode, backends, which fit this machine
make engine-plan ENGINE=vllm         # exact steps + launch rendered for this machine
make engine-check ENGINE=tensorfold  # blockers, e.g. "compute capability 8.6 < required 8.9"
make build-engine ENGINE=vllm        # build the engine's container image (see below)
make run-engine ENGINE=vllm MODEL=Qwen/Qwen2.5-0.5B-Instruct   # serve it: http://127.0.0.1:11434/v1
make engine-install ENGINE=mlx BACKEND=metal   # Metal only (no containers on macOS): uv tool install
make skills-validate                 # skills vs registry (CI); REGISTRY=<url> checks the live index
```

Build parameters come from the hardware, never from one hard-coded GPU:

| Parameter | Detected from | Used by (examples) |
|---|---|---|
| CUDA arch | `nvidia-smi` compute_cap (8.9 -> `-DCMAKE_CUDA_ARCHITECTURES=89`) | llama.cpp forks. Omitted when no GPU is visible (CI) |
| ROCm target | `rocminfo` (`gfx1100` -> `-DGPU_TARGETS=gfx1100`, `PYTORCH_ROCM_ARCH`) | llama.cpp forks, SGLang, FreeToken, ExLlamaV3 ROCm |
| CUDA major | `nvcc --version` | `mlx[cuda12|cuda13]`. CUDA-13-only wheels (SGLang, TensorRT-LLM, FreeToken) are blocked on 12.x |
| compute cap floor | `nvidia-smi` | TensorFold >= 8.9, TensorRT-LLM >= 8.0, vLLM/SGLang/MLX >= 7.5, Ollama >= 5.0 |

| Engine | Servable | Backends |
|---|---|---|
| llama.cpp, llama.cpp (PrismML fork) | yes | cuda, rocm, vulkan, metal, cpu |
| llama.cpp (LaurentZuijdwijk fork) | yes | vulkan (Strix Halo, RADV >= 25.3), rocm, cuda, cpu |
| Ollama | yes (checksum-verified release tarball, no systemd) | cuda, rocm, vulkan, metal, cpu |
| vLLM | yes | cuda, rocm, cpu |
| SGLang | yes | cuda (13), rocm (source) |
| TensorRT-LLM | yes | cuda (Linux, sm_80+) |
| FreeToken | yes | cuda (13), rocm (RDNA3/4) |
| Strata | yes (Qwen3.8-Flash-Next only) | cuda, rocm |
| MLX (mlx-lm) | yes | metal, cuda, cpu |
| TensorFold | yes | metal, cuda (sm_89+) |
| LiteRT (LiteRT-LM) | yes | metal, cpu |
| ExLlamaV3 (ROCm fork) | yes | rocm (RDNA3/3.5/4) |
| DFlash2 | via sglang (drafter) | cuda |
| MLX-fast (Bonsai 2) | via tensorfold / mlx (benchmark harness) | metal |
| WebLLM | no (browser-only) | — |

### Build every engine at its pin on demand (`engine-build.yml`, issue #614)

`ci.yml` builds only the images a PR **changed** (`CHANGED=<base>`) — that is the merge gate, and a
PR that touches no engine params builds nothing. There was no way to ask "build and verify *every*
engine at its committed pin, now" without pushing a commit that touched all of them.

`engine-build.yml` is that sweep, and it is deliberately **not** part of `ci.yml`:

```text
workflow_dispatch inputs
  engine  one engine id (e.g. llama.cpp); empty = every engine in the committed params
  arch    one backend (cpu|cuda|rocm|vulkan); empty = every variant of each engine
  push    true = publish the built images to GHCR; default false = build + verify only
  force   true = rebuild from scratch (--no-cache, no registry layer cache, fresh shared
          base); default false = reuse a cached or already-available image
```

**`force=true` + `push=true` is how every tag is rebuilt from a clean build and republished**
(issue #638). Without it the sweep can only ever validate `… available -> no rebuild`: a forced run
recompiles each cell and publishes it under three names — the immutable **hash tag**
(`<sha8>-<hash>-<variant>`), the moving **`:<arch>`** tag, and **`:latest`** (one variant per engine
carries it: the `cpu` variant when the engine has one, else its only/first variant, so parallel rows
never race on that tag). `make build-engine ENGINE=… ARCH=… FORCE=1` and `make build-engines FORCE=1`
do the same locally.

- `guard` first (owner or collaborator with write, before any secret is read), then the matrix.
- `matrix` runs `make engine-build-matrix ENGINE=… ARCH=…` — the rows are the **committed params**
  (`containers/engines/params/*.json`), never a hand-written roster, so a new variant is in the sweep
  the moment its params are committed. `make engine-build-matrix` is the same code
  (`scripts/engine_image.py matrix`) the CI matrix reads, with `--engine` / `--arch` filters.
- the same scopes are available locally from one target, in parallel — `make build-engines`
  (every engine × variant), `make build-engines ARCH=cuda` (one arch, every engine),
  `make build-engines ENGINE=llama.cpp` (one engine, every arch type), and
  `make build-engines ENGINE=llama.cpp ARCH=cuda` (one engine × one arch). Each row carries its own
  parameters, because they come from the engine's committed params for that backend.
- one `build` job per row, `max-parallel: 20`: `make build-engine ENGINE=… ARCH=…` then
  `make test-engine-stage ENGINE=… ARCH=… TEST=<row.test>` — `serve` for cpu (the image answers on
  the OpenAI API), `detect` for GPU (the binary reports its version and answers the flags a user
  types). Same make path as CI, so the verification is identical.
- no `pull_request`, `push` or `schedule` trigger. The row is **built, then verified, then**
  published — `make push-engine` is its own step, runs only when `push=true`, and re-checks the
  binary's flags before it pushes, so an image whose binary does not answer never reaches GHCR.
- **a narrow dispatch is not queued behind a sweep** (issue #621). The concurrency group is keyed by
  the selection for a build-and-verify run (`engine-build-build-<engine>-<arch>`) and shared by every
  publishing run (`engine-build-push`), so two pushes cannot race on the same `:<arch>` tag while
  `engine=llama.cpp arch=cpu push=false` runs **alongside** a full sweep. With the old constant
  `engine-build` group, such a dispatch was created with zero jobs and no runner until the sweep
  finished — indistinguishable from a dispatcher that does not work (measured: run 40199747645 behind
  run 40199122842). `cancel-in-progress: false` throughout: a sweep is never killed by a dispatch.

**Source or prebuilt is the params' decision, not this workflow's.** A variant with
`prebuilt: false` compiles from its pinned sha in the generated Dockerfile; a variant with
`prebuilt: true` starts `FROM` an upstream image and only adds the llgenie entrypoint. `llama.cpp` was converted to a source build in all four variants with this
change (pinned sha checked out, `-DGGML_*` flags, `-DCMAKE_CUDA_ARCHITECTURES` / `-DGPU_TARGETS`
passed to the compiler, only `build/bin` shipped on the slim runtime base). **12 variants are still
prebuilt** — `ollama` ×4, `vllm` ×3, `sglang` cuda, `tensorrt-llm` cuda — and converting them is
**issue #615**; this workflow builds whatever the params say, so a converted variant needs no
workflow change.

### Engine container images (one per engine x hardware arch)

**Plain make, no LLM.** The skills are read by one target only, `make generate-engine-params`.
Every build (`make install`, `make build-variant`, `make build-engine`, `make run-engine`,
`make test-engine`, CI) reads the generated, committed files under `containers/engines/`.
A unit test builds from a copy of the repo with `skills/` deleted.

**Order, for a new engine — what runs and what each step proves:**

1. `registry-sync` vendors the engine into `data/models.json` and files its tracking issue
   (`make spawn-engine-skill-issues`); `make check-engine-skill-gap` (ci-unit) keeps the sync PR
   red until the engine has a skill or a dated decision in `data/unsupported-engines.json`.
2. The skill lands as `skills/engines/<id>/SKILL.md`; `make skills-validate` refuses a malformed one
   and a `servable: true` linux engine whose container spec is absent.
3. `make generate-engine-params` writes the params, the binaries manifest and one Dockerfile per
   arch; `make check-engine-params` fails when what is committed differs from the skills.
4. `make check-engine-coverage` fails when the params exist but the matrix will never BUILD them — a
   cell in `DISABLED`, a variant outside `CI_VARIANTS`, or no `linux` image — unless the engine is a
   recorded `KNOWN_UNBUILT` exception. `make engine-coverage-report` prints the same census.
5. CI's `engine-image-*` matrix (`make list-engine-images CI=1`) builds each cell, `make
   test-engine-stage` runs its probe, `make push-engine` publishes it after that passes, and
   `engine-published-test` pulls it back and chats with it (`make test-published-engine`).

Steps 2–4 are one `make ci-unit` run on every PR; step 5 runs on the same PR and again on `main`.

Two steps that are never mixed:

```
make generate-engine-params          # skills -> params/<engine>.json + dockerfiles/<engine>/Dockerfile.<arch> (commit them)
make check-engine-params             # CI: fail if the committed params are stale
make check-engine-coverage           # CI: fail if a shipped servable engine has no buildable CI cell (disabled / no linux / no params) and no recorded exception
make engine-coverage-report          # the census: every shipped engine -> built | not-an-image | unbuilt (with its #103 reason)
make check-engine-source             # CI: fail if a cell says prebuilt=false but its install steps only download a wheel/archive
make check-model-links              # CI: every committed model/GGUF link a test depends on resolves (static, hermetic; LIVE=1 probes the real Hub via tests/hub_probe, the ONE liveness authority, issue #1000)
make model-links-report              # print those links and their callers (issue #1000)
make engine-source-report            # the census: source-built vs prebuilt cells, and every tracked exception
make build-engine ENGINE=llama.cpp-prism                 # image for THIS machine's backend (cuda here)
make build-engine ENGINE=llama.cpp-prism ARCH=rocm       # one image per backend: cpu | cuda | rocm | vulkan
make build-engine-base BACKEND=cuda                      # shared toolchain base (CI publishes it)
make build-engine-vllm-cuda                              # per engine x arch shortcut: build-engine-<engine>-<arch>
make build-engine-llama.cpp-prism-rocm
make build-engines                                        # EVERY engine x variant, in parallel (JOBS=, default nproc; VERIFY=1 runs each built image's binary test)
make build-engines FORCE=1 VERIFY=1                        # the same, every row rebuilt from scratch (--no-cache, fresh base) and verified
make build-engines ARCH=cuda                              # one arch, every engine
make build-engines ENGINE=llama.cpp                       # one engine, every arch type
make build-engines ENGINE=llama.cpp ARCH=cuda             # one engine x one arch
make engine-build-matrix [ENGINE=] [ARCH=]                # the JSON matrix the dispatched sweep builds
make run-engine ENGINE=vllm MODEL=Qwen/Qwen2.5-0.5B-Instruct PORT=11434
make stop-engine ENGINE=vllm
make list-engine-images              # every engine x arch variant
```

1. **`make generate-engine-params`** renders each skill into fixed, hard-coded
   parameters, **one image per backend** (`cpu`, `cuda`, `rocm`, `vulkan`). GPU code is a
   fat build, so one image covers every common card: CUDA `75;80;86;89;90;120` (Turing to
   Blackwell) and ROCm `gfx1030 … gfx1201` + `gfx942`. That makes 29 Dockerfiles instead of one
   per GPU arch.
   Each variant holds the base image, apt packages, build args, exact install steps (pinned
   sha, `-DCMAKE_CUDA_ARCHITECTURES=89`, `-DGPU_TARGETS=gfx1100`, CUDA wheel index, …),
   env, launch, health and `docker run` device args. A file is rewritten only when the
   rendered parameters differ.
   It also writes **one Dockerfile per engine x arch**
   (`containers/engines/dockerfiles/<engine>/Dockerfile.<arch>`). Each one starts `FROM` the engine's
   official image where one exists (`ghcr.io/ggml-org/llama.cpp:server[-cuda|-rocm|-vulkan]` pinned
   by digest, `vllm/vllm-openai[-cpu|-rocm]`, `ollama/ollama[-rocm]`, `lmsysorg/sglang`,
   `nvcr.io/nvidia/tensorrt-llm/release`), adding only the llgenie entrypoint.
   Otherwise it compiles on the CUDA/ROCm/ubuntu devel base and ships on a slim runtime base
   (llama.cpp family: multi-stage, only `build/bin` is copied). Compiled engines all build
   `FROM` one **shared toolchain base per backend** (`containers/engines/base/Dockerfile.<backend>`:
   CUDA/ROCm devel + cmake/ninja/git/uv), built once, published and reused, so the CUDA/ROCm
   layers are shared instead of repeated per engine.
2. **`make build-engine`** docker-builds that generated Dockerfile. No skill is read. The
   variant is picked from the detected GPU (else `<backend>-portable`) or set with
   `ARCH=`. The tag hashes the frozen variant (`llgenie/llama-cpp-prism:c96baf4a-<hash>-cuda-sm89`),
   so an unchanged engine is never rebuilt. With `LLGENIE_REGISTRY`, it is pulled instead.

Every image runs `containers/engines/entrypoint.sh` (`serve` | `health` | `detect` | `info` | `shell`),
`EXPOSE 11434`, and has a `HEALTHCHECK` on `/v1/models`. `make run-engine` publishes the port on
`127.0.0.1:$(PORT)`, mounts `~/models` at `/models`, and passes `--device nvidia.com/gpu=all` (cuda; host driver mounted via nvidia-container-toolkit CDI) or
`/dev/kfd`+`/dev/dri` (rocm). Before a cuda `docker run`, `make run-engine` creates a missing
`/dev/nvidia-modeset` with `nvidia-modprobe -c 0 -m -u` (CDI refuses to start when that node
is absent). Any AI harness then uses
`base_url=http://127.0.0.1:<PORT>/v1`, `model=llm-local`. Metal cannot run in a container,
so Apple Metal engines install natively as uv tools (`make engine-install BACKEND=metal`).
On cuda/rocm/vulkan/cpu, `make engine-install` refuses and points at `make build-engine`.
There are no host venvs: Python engines install into the image's Python.

**CI does the heavy lifting, with make only (no LLM).** `engine-matrix` computes the job list
from the committed params (`make list-engine-images CI=1 JSON=1`, 29 engine x backend variants, 25 built in CI while the 4 below are disabled).
`engine-base` publishes the 4 shared toolchain bases. Then `engine-image` runs one **parallel** job
per entry: `make build-engine ENGINE=… ARCH=…` builds with `docker buildx` using a GHCR
registry layer cache (`--cache-from`/`--cache-to`). A tag that is already published
(Dockerfile and params unchanged) is pulled, not rebuilt. The post-build test runs next in
`llgenie/test`: cpu images are started and tested on the published port (`make test-engine`:
`/v1/models` lists `llm-local` and `/v1/chat/completions` answers "hi"), GPU images print their
version (`make test-engine-image`). Only then `make push-engine` publishes the image to the
repo's GHCR, on every push run (feature branches too, for now). The push runs that check again and does not tag or push unless the engine binary
file exists in the image and **answers every flag the engine documents, one at a time**
(`binary_flags` in its skill: `--version` + `--help` for llama.cpp, ollama, vllm/cpu and freetoken and
the llama.cpp forks; `--help` for sglang, strata, tensorfold, litert, mlx, exllamav3 and tensorrt-llm).
**Every flag a user types is executed too** — `--version`, `-h`, `--help`, `-V` — and the help family
(`-h` or `--help`) and the version family (`--version` or `-V`) must each get an answer, so a release
that drops a whole spelling reds while an engine that only ever spelled it `--help` keeps passing
(issue #580). The check used to pass on the FIRST flag that answered, which is exactly how a dropped
`--help` shipped green; now each flag's own exit status and output are reported, and a flag that did
not answer is named in the failure. The bump PR's CI runs this through
`make test-engine-stage … TEST=detect` → `make test-engine-image` → `scripts/engine_image.py
test-image` + `tests/test_engine_version.py`, so a binary that cannot answer `--help` is red before a
human merges the bump. That row is decided by ONE function — `binary_file_works` in
`scripts/engine_image.py`, which passes the cell's engine id and variant to the decider — and the pytest
case calls it rather than probing again (issue #634: a local copy of the probe forgot the cell identity, so
`DEVICE_ONLY` was looked up under `("", "")` and the four device-only cells went red saying `and / is NOT on
the device-only exemption list`). `make engine-gate-report` prints what each cell will actually prove before any image
is built — `flag-proven`, `device-exempt` (with its reason) or `disabled` (issue #625) — so a sweep's green
rows can be read for what they are without opening 27 logs.
A Python import is not that check (issue #204). Those flags, and the file each image
must contain, are generated into `containers/engines/binaries.json` with the params
(`make generate-engine-params`, checked by `make check-engine-params`) and are NOT part
of the image-tag hash, so documenting them moves no published tag. **At least one probed flag must exit 0 — there is
no blanket `device` escape** (issue #625; until then vllm cuda/rocm, tensorrt-llm cuda and mlx cuda were green
with every probe at exit 1). The four cells whose CLI can only import WITH its device are named in
`DEVICE_ONLY` in `scripts/engine_image.py`, each with the measured reason and its issue; any other cell that
answers nothing is red, and the failure says to add it there deliberately or `DISABLE` it. A `detect` line
must also prove a **version shape** — a semver, or `pin <sha7+>` for an engine whose upstream prints none — so
`installed 0.00.000.272 I srv  llama_server: initializing ...` (a log timestamp, what the laurentzuijdwijk
fork's `--version` prints) and the placeholder `0.0.0` are failures, not versions.
A backend whose CLI
initialises its device at startup still has to CONTAIN the file, and (for the four named cells) the version
comes from `entrypoint.sh detect` (CI #106). A CLI whose parser has **no version flag at all**
(`binary_probe: help`: mlx cpu — argparse `--help`/`-h` only) must answer the help family,
and its version likewise comes from `detect`; without that policy the probe would fail an
engine for a flag it never had (found by the dispatch sweep, issue #614). When a `detect` has to fall
back because the installed distribution reports nothing usable (`0.0.0`, the ROCm wheel), the fallback
is the **pinned version** (`0.5.22`), never the commit sha: `pin 35ce3132…` is not a version, and
`make test-built-engine` rightly rejects it (#636/#650).
The second matrix `engine-published-test` (`test-published-<engine>-<arch>`) then pulls every
published image on a fresh runner, checks digest and version, starts the container and chats
"hi" (GPU images on CPU), and installs it from the registry only (issue #102). Finally
`install-published` tests `make install` itself per backend against the published images. Containers run with
`--shm-size 2g`; the ROCm source builds (sglang, freetoken) use the pinned
`rocm/pytorch` 7.2.4 base. Four images are disabled until issue #103 is fixed
(`DISABLED` in `scripts/engine_image.py`): llama.cpp-laurentzuijdwijk/cuda, exllamav3-rocm/rocm,
llama.cpp-prism/cuda and llama.cpp-prism/rocm. They are not built, installed or offered; on
cuda/rocm hosts `prism-server` uses the Prism cpu image meanwhile. Do not build the arch matrix on a
laptop: push and follow it with `make ci-engine-images` (`WATCH=1` polls until the run completes).
`engine-smoke-mac` installs ollama and mlx natively on macos-14 Metal. The smoke stage's tiny
model is fetched through `scripts/hf_download.py` — the one downloader — so a Hub 429 during the
parallel matrix waits the window out instead of failing the job that happened to run in it
(issue #385).

Every servable launch exposes the model as `llm-local` on the image's port 11434 (by flag,
`ollama create` / `litert-lm import`, a config alias, or a symlinked model dir when the
engine has no alias option). Engines are installed **only inside their container image**,
never on the host and never in a venv. Skills never use sudo or `curl | sh`. Format and
how to add an engine: [`skills/engines/README.md`](skills/engines/README.md).
