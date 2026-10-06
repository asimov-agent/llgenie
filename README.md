# llgenie

Tooling to pick and serve local LLMs through an OpenAI-compatible endpoint (`llm-local`).
On Linux every inference server (llama.cpp, Prism, vLLM, Ollama, ...) runs from its
CI-tested container image pulled from GHCR (`cpu | cuda | rocm | vulkan`); on macOS Metal,
llama.cpp is built natively. Also included: a resilient Hugging Face downloader and the
Python venv scaffold the launcher needs.

This repo bundles three pieces that were built and validated together:

| Piece | File | What it does |
|---|---|---|
| **GGUF launcher + auto-tuner** | `scripts/llama_serve.py` | Scan `~/models/**/*.gguf`, pick a model (and engine, `--pick`), auto-tune `llama-server` flags to the detected card RAM, and serve an OpenAI-compatible endpoint at `127.0.0.1:11434`. |
| **HF downloader** | `scripts/hf_download.py` | Download a GGUF into a tiered models folder with live progress and auto-resume/auto-retry against a throttled Hugging Face CDN. |
| **venv setup** | `tools/` | `gguf`-tooling environment (Python 3.10 venv + pip-compile container), recreatable via `make venv-install`. |

---

## Requirements

- **Linux/PC: Docker.** Every inference server, llama.cpp included, runs from its
  container image; nothing is compiled on the host. NVIDIA hosts also need
  nvidia-container-toolkit with a CDI spec (see "Backend selection"). `make install` pulls the
  published images (`BUILD=1` builds unpublished ones) and writes a
  `~/bin/llama-server` shim (stock llama.cpp image) and a `~/bin/prism-server` shim
  (Prism image). On macOS (Metal), a native
  llama.cpp build is used instead (`make install-prism-metal` / `install-upstream-metal`).
- **macOS** with an Apple Silicon GPU for the native Metal path (card RAM is detected;
  `TOTAL_RAM_BYTES` = 48 GB is only the fallback when detection fails).
- **Python 3.10** (Homebrew: `brew install python@3.10`) for the `gguf` tooling venv.
- Optional `hf` CLI (Hugging Face hub) in a venv — used by `scripts/hf_download.py`.

---

## Install (recommended) — one command, no manual venv work

```bash
git clone <this-repo> ~/repository/git/llgenie
cd ~/repository/git/llgenie
make install
```

`make install` does the whole setup so you never touch the venv by hand:

1. **venv** — builds the Python 3.10 gguf-tooling venv at `~/llama-gguf-tools/.venv`
   (`numpy` + `gguf==0.19.0` + `huggingface_hub[cli]` so the `hf` downloader used by
   `--download-top-tier` is always available, no separate install needed).
2. **launcher** — writes an executable `~/bin/llgenie` that runs `scripts/llama_serve.py` **with the
   venv's python**, so `gguf`/`numpy` resolve with zero extra steps.
3. **engine images + start scripts** — pulls this host's backend images from GHCR
   (`LLGENIE_REGISTRY`, default `ghcr.io/asimov-agent`): by default llama.cpp + Prism,
   `ENGINES=all` for every engine; other engines are pulled on first use by `llgenie --pick`.
   `BUILD=1` builds an unpublished image from its generated Dockerfile. It writes
   `~/bin/llgenie-engine-<id>` per engine (`--version`, or `<model> [port]` to serve it as
   `llm-local` on `127.0.0.1:<port>/v1`), plus two shims that take the llama-server CLI:
   `~/bin/llama-server` runs the stock llama.cpp image, `~/bin/prism-server` the Prism image
   (llgenie uses prism-server on cards <= 24 GB, llama-server above). `ENGINES=llama.cpp,vllm` limits the set.
   Then `make test-built-engine` runs every start script with `--version`; install fails
   unless each one prints its engine version through its image.
4. **symlink + smoke** — symlinks `~/bin/llgenie.py` → this repo's launcher (`scripts/llama_serve.py`),
   then runs `~/bin/llgenie --list`. Succeeds even when `~/models` is empty (you populate it with
   `llgenie --download-top-tier`), failing only on a genuine gguf/launch error.
5. **PATH** — if `$HOME/bin` is not already on `PATH` in the default shell's rc file,
   adds `export PATH="$HOME/bin:$PATH"` at the top of `~/.bashrc` (login shell bash)
   or `~/.zshrc` (login shell zsh). An existing line is left unchanged.

### `llgenie`: trending model + fastest engine (issue #105)

`llgenie` with no model is interactive:

1. **The trend list**: exactly the [trending-local-llms](https://github.com/andyholst/trending-local-llms)
   README "Most loved" list, in README order (🔥 trending -> 🕑 recent -> 💤 stale, then trend score),
   every model whose README VRAM column fits this card (a 16 GB card is 16 GB even though
   `nvidia-smi` reports 15.99 GiB). Every model you can run here is numbered, downloaded or not
   (`[local]` = already in `~/models`); one that cannot run here stays in the list as `--` with the reason.
2. **Engines** for the chosen model, each with the format llgenie fetches for it: figures
   measured on this host's kind of hardware first (RTX for cuda, Radeon/Strix Halo for rocm/vulkan,
   CPU for cpu), then figures from other hardware labelled `(ROCm)` / `(CPU)` / `(Metal)`, then
   engines the registry lists as supported without a figure.
3. **Download** when missing, in the engine's format:
   - `gguf`: the registry's GGUF repo, else the most-downloaded `<name>-GGUF` repo; the largest GGUF
     within 80% of the card minus 1 GiB (16 GB -> 11.8 GB). MoE models add system RAM minus 4 GiB
     (llama.cpp keeps the experts in RAM). Split models: all shards. Never MTP heads, imatrix or mmproj.
   - `litertlm`: the generic `.litertlm` of the registry repo (not the gpu/web/vendor builds).
   - `mlx-safetensors` / `safetensors`: the whole registry repo (config + weights).
4. **Serve** through `~/bin/llgenie-engine-<id>` (image pulled on first use) on
   `127.0.0.1:<port>/v1` as `llm-local`.

Without a terminal:

```bash
llgenie --trend                 # print the numbered list and exit
llgenie --select 4              # take row 4: download it if missing, serve with its top engine
llgenie --select 2 --engine llama.cpp --dry   # row 2 on llama.cpp; --dry = print the plan only
```

`--auto` (or no terminal) takes the top model and its top engine without asking.

Manual mode, compatibility checked (image for this host + the engine skill's `formats`
include the model's format; otherwise llgenie exits naming the compatible engines):

```bash
llgenie --list                         # local models
llgenie --engines                      # engines with a published image for this host
llgenie --engines qwen3-8b             # engines that can run that local file / registry model
llgenie qwen2.5-0.5b --engine ollama   # this local model on this engine
llgenie --pick bonsai --engine prism   # this registry model on this engine (downloads if missing)
llgenie --pick bonsai --engine prism --model-file ~/models/Ternary-Bonsai-2-27B-PTQ1_0-mtp.gguf
llgenie qwen2.5-0.5b                   # local model on llama.cpp (prism-server / llama-server by card size)
llgenie --local                        # pick among local files, llama.cpp
```

The registry is `data/models.json` (with the README it was generated with, `data/trending-README.md`), a verbatim copy of
[trending-local-llms](https://github.com/andyholst/trending-local-llms) `data/models.json`
(no live fetch at run time; `LLGENIE_REGISTRY_SRC=<file|url>` overrides it):

```bash
make sync-registry    # download upstream data/models.json + README.md into data/ (validated: the
                      # registry must be the README "Most loved" list in README order)
make check-registry   # validate the vendored files (CI)
```

The `registry-sync` workflow runs `make sync-registry` daily and opens a PR when it changed.

After `make install`, just run:

```bash
llgenie                 # trending models that fit this card -> engine -> download -> serve
llgenie --list          # list local models
llgenie qwen            # launch a local model by name substring (llama.cpp)
llgenie --dry           # print the pick and the command without running
```

Other targets: `make venv-install`, `make link`, `make smoke`, `make list`,
`make version`, `make uninstall` (removes the launcher, symlink and every start script,
keeps the venv), `make help`.

CI tests every engine image twice. The build job tests it right after the build
(`make test-engine` / `make test-engine-image`) and only then pushes it to GHCR
(`make push-engine`, every push run, feature branches too). The separate `engine-published-test`
matrix (one job per image, `test-published-<engine>-<arch>`) then pulls each image back from GHCR on a fresh runner (`make test-published-engine`:
no local build, digest of the pinned tag == `:<arch>`, binary version, then the container is
started and must answer "hi" on `/v1/chat/completions`; GPU images of the llama.cpp family
and Ollama run without GPU devices and fall back to CPU, GPU-only engines such as vLLM or SGLang
get the version test on their GPU images), and installs from the registry only
(`make engine-launchers` + `make test-built-engine`). The last stage, `install-published`,
runs the real `make install` per backend (cpu/cuda/rocm/vulkan mocked via `LLAMA_BACKEND`, GPU
images on CPU) against those published images: only that backend's images are pulled, llgenie
answers "hi" through `llama-server` and `prism-server`, `llgenie --pick --engine` pulls the
picked engine on first use, and `make uninstall` leaves nothing behind.

CI runs this exact path on a clean runner: the `install` job runs `make test-install-ci`
(`make install` -> `make test-built-engine` -> install tests -> llgenie answers "hi"
through the container shim (`llama-server` / `prism-server`) -> `make test-install-trend`:
the installed `llgenie` with no model runs in a pty, picks the top recommendation and engine
from `data/models.json`, downloads the GGUF and the engine container answers "hi" -> `make uninstall`).
Each `install-published-<backend>` job also runs the trend pick (`--dry`) from the installed `llgenie`.

> **Why a wrapper?** `scripts/llama_serve.py` imports the `gguf`/`numpy` packages that live in the
> venv, so it must be launched with the venv python. The `~/bin/llgenie` wrapper does
> exactly that; the `llgenie.py` symlink keeps editors/`--list` pointing at the real file (which lives at
> `scripts/llama_serve.py`).

### Manual setup (only if you don't want `make install`)

```bash
# 1. venv
cd tools && make venv-install      # create ~/llama-gguf-tools/.venv + install deps
# 2. run with the venv python
~/llama-gguf-tools/.venv/bin/python scripts/llama_serve.py --list
```

`requirements.in` is the single source of truth; `requirements.txt` is generated with
`pip-compile` inside the `tools/` Dockerfile container (`make generate-requirements`).

## Which llama.cpp build is used (card-size rule, issue #84)

`make install` picks the llama.cpp **tree** (upstream or Prism) and the **backend** from the
hardware and installs the matching **engine image** (`llgenie/llama-cpp` or
`llgenie/llama-cpp-prism`, `:cpu|cuda|rocm|vulkan`): pulled from GHCR when published, built
from its generated Dockerfile otherwise. `~/bin/llama-server` is a shim that runs the stock llama.cpp image and `~/bin/prism-server`
the Prism image (llgenie picks by card tree);
nothing is compiled on the host (only macOS Metal builds natively, see below).

### Tree selection — card RAM only (no model quant inspection)
Card RAM means the GPU's VRAM when an NVIDIA card is present (via `nvidia-smi`),
otherwise the system RAM. `LLAMA_RAM_BYTES` is a test/CI seam, not a user knob.

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
make install-prism-metal     # macOS only: native Metal build (Metal cannot run in a container)
make install-upstream-metal  # macOS only
make uninstall               # removes the launcher, llgenie.py, every llgenie-engine-* start script and the
                             # llama-server / prism-server shims; stops llgenie engine containers (PURGE_IMAGES=1: images too)
# native builds only (macOS Metal / CI server-variants-mac); on Linux use make run-engine
make serve-variant TREE=prism BACKEND=metal          # serve the built binary on a free port
make serve-variant TREE=prism BACKEND=metal PORT=18080
make test-serve-variant TREE=prism BACKEND=metal     # "hi", then stop that server
make stop-serve-variant TREE=prism BACKEND=metal     # stop only the server make started
```

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
- `LLAMA_BACKEND` = metal | cuda | cpu (| rocm | vulkan for engine skills)  (override hardware detection)
- `LLGENIE_CUDA_ARCH` / `LLGENIE_CUDA_VERSION` / `LLGENIE_GPU_TARGETS` / `BUILD_JOBS` (engine-skill hardware params)
- `LLAMA_RAM_BYTES` = card RAM in bytes (test/CI seam)
- `LLAMA_SERVER_TREE` = prism | upstream (force the tree, independent of card RAM)
- `LLGENIE_REGISTRY` = registry to pull/push engine images (default `ghcr.io/asimov-agent`)
- `LLGENIE_NO_GPU=1` = start GPU images without GPU devices (CPU fallback; used by CI)
- `LLGENIE_MODELS_DIR` = models dir the start scripts mount (default `~/models`)

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

### Engine container images (one per engine x hardware arch)

**Plain make, no LLM.** The skills are read by one target only, `make generate-engine-params`.
Every build (`make install`, `make build-variant`, `make build-engine`, `make run-engine`,
`make test-engine`, CI) reads the generated, committed files under `containers/engines/`.
A unit test builds from a copy of the repo with `skills/` deleted.

Two steps that are never mixed:

```
make generate-engine-params          # skills -> params/<engine>.json + dockerfiles/<engine>/Dockerfile.<arch> (commit them)
make check-engine-params             # CI: fail if the committed params are stale
make build-engine ENGINE=llama.cpp-prism                 # image for THIS machine's backend (cuda here)
make build-engine ENGINE=llama.cpp-prism ARCH=rocm       # one image per backend: cpu | cuda | rocm | vulkan
make build-engine-base BACKEND=cuda                      # shared toolchain base (CI publishes it)
make build-engine-vllm-cuda                              # per engine x arch shortcut: build-engine-<engine>-<arch>
make build-engine-llama.cpp-prism-rocm
make build-engines ARCH=cuda                             # every engine for one arch
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
   `ARCH=`. The tag hashes the frozen variant (`llgenie/llama-cpp-prism:2459f68b-<hash>-cuda-sm89`),
   so an unchanged engine is never rebuilt. With `LLGENIE_REGISTRY`, it is pulled instead.

Every image runs `containers/engines/entrypoint.sh` (`serve` | `health` | `detect` | `info` | `shell`),
`EXPOSE 11434`, and has a `HEALTHCHECK` on `/v1/models`. `make run-engine` publishes the port on
`127.0.0.1:$(PORT)`, mounts `~/models` at `/models`, and passes `--device nvidia.com/gpu=all` (cuda; host driver mounted via nvidia-container-toolkit CDI) or
`/dev/kfd`+`/dev/dri` (rocm). Any AI harness then uses
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
repo's GHCR, on every push run (feature branches too, for now; `pull_request` runs never push).
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
`engine-smoke-mac` installs ollama and mlx natively on macos-14 Metal.

Every servable launch exposes the model as `llm-local` on the image's port 11434 (by flag,
`ollama create` / `litert-lm import`, a config alias, or a symlinked model dir when the
engine has no alias option). Engines are installed **only inside their container image**,
never on the host and never in a venv. Skills never use sudo or `curl | sh`. Format and
how to add an engine: [`skills/engines/README.md`](skills/engines/README.md).

## Download a model (`scripts/hf_download.py`)

```bash
python3 scripts/hf_download.py <repo_id> <filename> <dest_dir> <label>
```

- Reads `HF_TOKEN` from `~/.zshrc` at runtime (never stored in the repo).
- Sets `HF_HUB_ENABLE_HF_TRANSFER=1 HF_HUB_DISABLE_XET=1` for speed.
- Auto-retries (up to 20 attempts), resuming the partial file on dropped connections.
- Appends a `.progress.log` next to the destination for live monitoring.

**Example:**

```bash
python3 scripts/hf_download.py Qwen/Qwen3.5-24B-GGUF qwen3.5-24b-q5_k_m.gguf ~/models/Qwen/24GB qwen-q5
```

## 3. Launch a model (`scripts/llama_serve.py`)

Run with the tooling venv's Python so `gguf`/`numpy` are importable:

```bash
~/llama-gguf-tools/.venv/bin/python scripts/llama_serve.py --list     # list models, don't run
~/llama-gguf-tools/.venv/bin/python scripts/llama_serve.py <name>     # run by substring
~/llama-gguf-tools/.venv/bin/python scripts/llama_serve.py            # interactive picker
~/llama-gguf-tools/.venv/bin/python scripts/llama_serve.py --dry qwen # print the command, don't run
```

The launcher will:

- Scan `~/models/**/*.gguf` (fast header-only metadata read for large files).
- Auto-tune the server context (`-c`) from the **selected model**. The ceiling is
  that GGUF's `context_length` (Ternary Bonsai 2 is 262144). The window is lowered
  only when the q4_0 KV cache for that context does not fit in card RAM (NVIDIA
  VRAM when a GPU is present, otherwise system RAM) after the weights and a 3 GB
  reserve. Hybrid models (a `full_attention_interval` in the header) count only
  the full-attention layers, plus an MTP block when the file has one. The result
  is a multiple of 1024 and is never below 2048. On a CUDA or Metal backend,
  `-ngl` is 99 when the weights and that KV cache fit, and a smaller layer
  count when they do not. `-fa on` is set only for those GPU backends.
  `-ctk`/`-ctv` stay `q4_0` so the cache matches the `-c` budget. `-b`/`-ub`
  are 512/256 up to 8 GB, 2048/512 up to 24 GB, and 4096/1024 above that.
  `--jinja` is set only when the GGUF has a chat template. `--cont-batching`
  and `--metrics` are always on. A Prism low-bit file (`PTQ1_0`, `PQ2_0`,
  `TQ1_0`, `TQ2_0`) with no author sampling block uses Bonsai's defaults
  (`--temp 0.5`, `--top-p 0.85`, `--top-k 20`, `--min-p 0`). Its `-c`, `-ngl`,
  and batch still follow that file and the card.
- Detect reasoning-capable models from the chat template and enable `--reasoning` /
  `--reasoning-format deepseek` so thoughts are preserved in `message.reasoning_content`.
- Serve **one model at a time**: any existing `llama-server` on the port is stopped before
  launch. Default port `11434`, override with `--port`.
- Serve under a **stable alias `llm-local`** (`--alias llm-local`) so OpenAI-compatible
  clients can pin one endpoint name regardless of which model is loaded.
- Engage **MTP (multi-token-prediction)** spec-decode when the model carries a
  draft head (`nextn_layers` in the GGUF, e.g. Ternary-Bonsai-2 MTP /
  Qwen3.8-27B MTP), with the speed knobs **derived from the card's RAM** (the
  same card RAM that picks Prism-vs-upstream, via `detect_card_ram_bytes`), per
  the [qwen38-mtp](https://github.com/sudoingX/qwen38-mtp) community rules:
  - `--spec-draft-n-max` (depth) **card-class driven, never hard-coded**: card
    RAM `<= 16 GB` -> `1`, `16 < RAM <= 24 GB` -> `2`, `> 24 GB` -> `3`.
  - `--spec-draft-p-min` **never a default** (rule 2: helps starved cards, hurts
    fast ones) — emitted only when the seam `LLAMA_SPEC_DRAFT_P_MIN` is set.
  - `--parallel` **pinned to `-np 1` when MTP is engaged**, regardless of model
    size (rule 5: spec decode is a single-stream optimisation; `--parallel > 1`
    kills the gain). Without MTP, the size-based rule stands (`-np 2` for models
    `< 10 GB`).
- Write the exact command to `<model-dir>/.run.log` for audit/replay.

You can customize `TOTAL_RAM_BYTES`, `OS_OVERHEAD`, `KV_QUANT`, and `SAMPLING` at the top
of `scripts/llama_serve.py`. For `--download-top-tier`, the fit is **dynamic**: the total
comes from the actual card (`LLAMA_RAM_BYTES` overrides it), headroom is capped at 45% of
total, and KV reserve applies automatically.

### Test the endpoint

```bash
curl http://127.0.0.1:11434/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"llm-local","messages":[{"role":"user","content":"hi"}]}'
```

## Download the top-tier trending models that fit your GPU (`--download-top-tier`)

Discover and download the **currently-trending, top-tier** GGUF models (from the Hugging
Face community that publishes GGUF for llama.cpp) that **fit the CPU/GPU card you actually
have** — with KV-cache headroom so they *run*, not just download.

```bash
# list the top-tier trending models that fit the actual card (no download)
llgenie --download-top-tier --list
# download 5 distinct providers x 2 quants (default): each provider's HIGH (Q8) + lower (Q6/Q5)
llgenie --download-top-tier
# download N providers' high + lower quants (--count) 
llgenie --download-top-tier --count 3
# just the best (high) quant per provider, no lower
llgenie --download-top-tier --per-provider 1
# only consider models rated high enough (trendingScore floor)
llgenie --download-top-tier --min-trending-score 150
# see what it would download without downloading
llgenie --download-top-tier --dry
```

By default it aims for **5 distinct providers × 2 quants each** — the HIGH (Q8) plus a clearly-LOWER
(Q4/Q5/Q6) quant per provider — **ranked by trending** (most popular now first, not by file size),
and it **only downloads — it never auto-starts llama-server** (serve a downloaded model separately
with `llgenie <name>`). A failing provider is retried (up to 3×) without aborting the batch, and
already-downloaded models are never re-fetched on a re-run (idempotent via HF content-hash). Live
download progress shows a **0-100%** readout of the current file, and it uses HF's high-performance
`hf-xet` transfer (fast for large files).

How it decides "trending + top tier + fits":

- **Trending** — a time-weighted Hugging Face popularity signal (`trendingScore`,
  `filter=gguf`), so you get what's hot *now*, not a lifetime download count.
- **Top tier** — only flagship/large popular families (Qwen3, DeepSeek, Mistral, Llama,
  Gemma, gpt-oss, Phi, QwQ, GLM, Olmo, plus trending additions Ornith/Qwopus/Qwythos/
  Tiel-Coder/MiniMax/K2 so popular trending LLMs aren't dropped), and only non-trivial
  quant files (no sub‑1B toy quants, no multi-file shards, no vision projectors) — plus
  it drops **low-fidelity IQ1/IQ2/IQ3 quants** (an 8-11 GB "27B" is poor quality) and
  **MTP/mtp-* companion heads** (multi-token-prediction aux files, not the serviceable
  model), and still excludes non-LLM repos (TTS, image/audio encoders).
- **Fits with buffer** — the total memory comes from the **actual card** at runtime
  (`sysctl hw.memsize` on macOS, `/proc/meminfo` on Linux, or `LLAMA_RAM_BYTES`), with
  current-pressure headroom (`vm_stat`). Only models that leave a KV-cache reserve are
  offered — on a 48 GB card that's ~29 GB Q8-class 27B models; on a 16 GB CPU card it
  downshifts to ~12 GB Q3-class.

Downloads go into a **provider-aware** folder so you always know who made the model, and the
downloaded file is **verified by its GGUF metadata** (architecture / name / layers) before it's
accepted — an HTML error page, truncated/corrupt stub, or wrong-model-under-right-name is rejected:

```
~/models/<owner>/<family>/<TierGB>/<file>.gguf
~/models/unsloth/Qwen3.8-27B/48GB/Qwen3.8-27B-UD-Q8_K_XL.gguf
```

The `TierGB` folder is **dynamic and bounded by the card that runs the model** — it's the
smallest available bucket ≥ the model size, from a growing ladder (1/2/4/8/16/24/48/96/128/
192/256/384/512/...), where only buckets ≤ the detected/overridden card exist. So a **48 GB
card keeps the classic 8/16/24/48** folders (plus truthful 1/2/4 small tiers), a **small
CPU/container card gets truthful 1/2/4/8 folders** for tiny models, and a **256/512 GB card
also gains large tiers** and labels a 400 GB model `512GB/` (never misleadingly `48GB/`):

```
48 GB card:  29GB -> 48GB/   47GB -> 48GB/   0.43GB -> 1GB/   (truthful small tiers)
8 GB card:   0.5B -> 1GB/   1.5B -> 2GB/    3B/7B -> 4GB/    (real CPU/container models)
512 GB card: 60GB -> 96GB/  100GB -> 128GB/  400GB -> 512GB/
```

Re-runs are **idempotent**: the real `hf` (huggingface_hub) CLI content-addresses its cache
by etag, and the launcher skips entirely when the target file is already complete — so you
never re-download the whole model.

**Only listed are models that can actually download.** Before the batch commits, every
candidate is **pre-flight probed**: `--download-top-tier` fetches a real ~64 KiB chunk of
each file (a ranged request) and verifies it is genuine GGUF data over an authenticated 200
— so **gated (403/401 "requires approval")**, **dead (404)**, and **200-but-HTML/error-shell**
repos are **skipped fast** (one cheap probe, not 3 slow failed downloads) and logged clearly:
`[top-tier] skipping <repo>::<file>: access-denied (403)`. The list is then **refilled from
the next fitting provider**, so the requested `--count × --per-provider` total is honored even
when some trending repos are unreachable — no more silent "8 of the intended 10". The final
report shows `downloaded N/M (+S skipped: access-denied, dead)`.

### Scope to ONE model family (`--download-top-tier --family <keyword>`)

`--family <keyword>` narrows the same top-tier pipeline to the **top `--count`
providers (HF owners) of ONE model family** (e.g. `qwen`, `ornith`) — each with
its HIGH (Q8) + LOWER (Q4/Q5/Q6) quant — instead of trending across *all*
families. A niche family has 0–2 repos in the global trending window, so this
queries the **complete** family for the keyword rather than the trending slice.

```bash
# top 5 providers of the qwen family, each with high + lower quants
llgenie --download-top-tier --family qwen
# top 1 provider of the ornith family, just the high quant
llgenie --download-top-tier --family ornith --count 1 --per-provider 1
# preview a known low-end family, 1 provider, without downloading (small card)
LLAMA_RAM_BYTES=$((8*1024**3)) llgenie --download-top-tier --family qwen --count 1 --dry
```

Everything else (`--count`, `--per-provider`, `--dry`, placement, probe+refill,
`hf` download) works exactly as the trending path — family mode is a *filter*
fed into the **same** pipeline, not a second implementation:

- **Word-boundary match, not substring.** `--family qwen` matches
  `unsloth/Qwen3.8-27B-GGUF` / `Qwen/Qwen2.5-0.5B-Instruct-GGUF` (the keyword may
  be followed by a version digit, e.g. `qwen2`/`qwen3`) but **never** a different
  family that merely starts with the same letters — `Jackrong/Qwopus…`,
  `empero-ai/Qwythos…`.
- **`--min-trending-score` is ignored in family mode** (a score floor would filter
  a niche family out entirely — most family repos report trendingScore 0). Family
  providers are ranked trendingScore desc with a **downloads desc tie-break**.
- **Degenerate families fail loudly, never silently:** a keyword with **zero**
  matching GGUF repos prints `no GGUF repos found for family '<kw>'` and exits
  non-zero (typo / non-GGUF family); **fewer** providers than `--count` downloads
  what exists and reports honestly (`downloaded N/M`).
- **Transient HF API errors are retried** (this applies to the whole top-tier
  pipeline, trending *and* family). Family mode fans out one HF API call per repo
  tree (hundreds), so the pipeline retries rate-limits / server blips
  (HTTP 429/500/502/503/504 and plain network / socket-timeout errors) with
  bounded exponential backoff that honours `Retry-After`; a **permanent** error
  (401/403/404) is never retried — it fails fast so a genuinely gated/dead repo is
  still reported loudly (the skip+refill and "no repos" paths above). Without this
  retry, a single 429 on one repo tree would silently drop that repo and turn a
  valid match into a false "no model fits".

Without `--family` the command behaves byte-identically to before (all existing
top-tier tests pass unmodified).

---

## Verification, loop & CI (containerized — same everywhere)

Every verification stage runs **inside the test container** so behaviour is
byte-identical on your local host (nerdctl/Colima or docker) and on GitHub
Actions CI. Stages are driven **only through `make`** — the container is never
started directly.

```bash
make loop              # == make loop-harness: run ALL stages in order, GREEN gate
make test-image        # build the test image (python+pytest+deps + hf + docker CLI; no inference server)
make lint              # linefeed/editorconfig lint (fail-closed)
make test-unit         # hermetic unit tests (all files, incl. openspec-tasks-check)
make test-agents-e2e   # REAL agent-spawn e2e: runs ONLY *_e2e*.py — fake worker does README
                       # issue-work, hung worker is killed+respawned (issue #63); <1 min
make test-install      # install tests (run in-container; host-artifact asserts — no skips via test-install-ci)
make test-install-ci   # REAL install tests, NO SKIPS: make install + model + assert in ONE container
make test-install-host # verify the REAL host install: ~/bin/llgenie + symlinks + ~/models (runs on host)
make test-health       # end-to-end CPU LLM check: downloads tiny model, answers "hi"
make test-top-tier     # REAL acceptance (no mocks): live HF trending + fit gate + real download
make test-top-tier-serve  # download a lightweight top-tier model, load llama-server, answer 'hi', check RAM
make test-top-tier-cli-ci # REAL CLI dry-run in the CI container: llgenie --download-top-tier --dry --count 2
make download-test-model  # fetch Qwen2.5-0.5B into ~/models/Qwen/8GB (via `hf` CLI)
make openspec-validate NAME=<change>   # validate an OpenSpec change
make test-clean        # prune stopped orphaned test containers (always)
```

The `make loop` harness runs these stages in order (each in its own `--rm`
container), then **always** prunes orphaned containers:

```
image → download → lint → unit → install → health → top-tier → top-tier-serve → test → openspec → clean
```

- The **`health` stage** is a real end-to-end check: it downloads the
  lightweight `Qwen2.5-0.5B` model and asserts `/health` + a chat "hi" reply
  from the **llama.cpp engine image**, started from the test container through the host docker socket (the test image holds no inference server).
- **`RUNTIME`** defaults to `nerdctl` and resolves to `docker` on non-Colima
  hosts — the same `make` target runs under either engine.
- **CI** (`.github/workflows/ci.yml`) triggers on every branch/PR and runs each
  stage as its own **parallel** job: `lint`, `unit`, `install`, `openspec`,
  and `cpu-health`. Every job is a `make` command, so CI == your local loop.

### No-fallback rule

The repo has **one** code path per resource, running through the same container
on CI and locally. In particular the model download always uses the official
`hf`(huggingface_hub) CLI (bundled in the test image) — never a `requests`/
`urllib` fallback.

### Local GPU (Metal) verification is mandatory

CI exercises only the **CPU** path (bare runners, no GPU). Before reporting a
change that touches the launcher/health/serving as done, you must also run the
health check against the **host GPU (Metal)** via `~/bin/llgenie` with the
`Qwen/8GB` model and record the reply.

### Self-driving development (background watch loop)

This repository is **self-driving** when its background watch loop is installed
on the host. A `*/20 * * * *` host crontab entry launches a one-shot
`project-manager` Hermes session (cwd = this repo, so `AGENTS.md` loads as its
durable rulebook) that, each tick:

- **Polls PRs + CI first** and merges any PR whose CI is fully green AND has an
  approval AND no open review threads, then cleans up the merged branch — the
  local worktree + local branch + per-worker artifacts **and the REMOTE branch**
  (`git push origin --delete feat/<kebab>`; the merge itself also requests
  `delete_branch: true`, so no stale `origin` branches accumulate after a merge).
- **Drives every open issue to a PR**: for any open issue lacking a live branch/
  PR it creates an isolated git worktree feature branch off `main`
  (`../llgenie-wt/<kebab>`), follows the OpenSpec-first lifecycle
  (change/proposal/spec/tasks first, then implementation), validates, then opens
  a PR against `main` that references the issue.
- **Keeps the issue body, OpenSpec change, and code in sync** (bidirectional,
  continuous).
- **Reclaims only genuinely dead or long-silent workers.** Each worker writes a
  spawn-wrapper heartbeat line to its own `feat-<slug>.log` every
  `WORKER_LOG_HEARTBEAT_SECONDS` (default 5 min) while its hermes child is alive, so
  the loop's liveness check never mistakes a productive-but-slow worker for a hung
  one (`hermes chat` buffers all stdout until it exits — it never streams mid-run).
  A worker is only reclaimed as stuck after its log has been silent for
  `STUCK_LOG_STALE_SECONDS` (default 4 h, far beyond the heartbeat cadence), and a
  worker whose process has exited is reclaimed immediately via the dead-PID path.

The durable rules and the exact crontab entry live in `AGENTS.md` (the
"Background watch loop" section); the loop prompt and its output log are
`.watchloop/prompt.txt` and `.watchloop/watchloop.log` (both gitignored). You can
review past loop runs with `grep 'WATCH-LOOP SUMMARY' .watchloop/watchloop.log`.

This contract is exercised end-to-end by verification issue
[#7](https://github.com/asimov-agent/llgenie/issues/7), which the loop drove to a
real worktree → OpenSpec → code → PR lifecycle on the branch
`feat/test-watchloop-verify-the-background-watch-loop-dr` — proof the loop is not
just documented but actually drives a brand-new issue to a PR.

### Choosing the worker model the loop uses

Each cron-spawned worker is a `project-manager` Hermes session that drives one open
issue to a PR. It uses an LLM whose choice defaults to the local GGUF model
(`llm-local` on `:11434`, good for serving) but is **configurable** so the loop runs
fast when you want it to.

**Where it is set — two places (resolution order, first wins):**

1. **Environment variables** (in the crontab / exported): `WATCHLOOP_WORKER_MODEL`
   and `WATCHLOOP_WORKER_PROVIDER`.
2. **The config file** `.watchloop/run/worker-model` — two lines, line 1 = model id,
   line 2 = provider (blank = profile provider). This is a **local, gitignored** file.

If both are empty, workers use the profile default (`llm-local`).

**How to configure (recommended, uses the template):**

```bash
# copy the versioned template into the live (gitignored) config, then edit it
cp scripts/worker-model.template .watchloop/run/worker-model
```

A built-in template lives at **`scripts/worker-model.template`** (tracked in git) and
documents both options in place:

- **llama.cpp / local GGUF** — set line 1 to `llm-local`, leave line 2 empty. Good
  for offline/private jobs; slower for agentic driving (~170s/call on the 35B).
- **Hosted / OpenRouter (recommended for speed)** — e.g. line 1
  `deepseek/deepseek-v4-flash-0731`, line 2 `openrouter`. Makes the autonomous loop
  drive issues to a PR quickly.

The dispatcher reads this at startup and launches each worker with
`hermes chat ... -m <MODEL> --provider <PROVIDER>`. Change the file (or the env vars)
and the next cron tick picks it up.

### Installing / uninstalling the watch loop (macOS + Linux)

The watch loop runs as a host crontab entry (`*/20 * * * *`). Two `make` targets
install and uninstall it idempotently (guarding against duplicates and preserving
your other crontab lines):

```bash
make cron-install      # add the */20 watch-loop entry (idempotent; no-op if already present)
make cron-uninstall    # remove ONLY the watch-loop entry (keeps unrelated lines)
make cron-snapshot     # (via scripts/install_watchloop_cron.py snapshot) preview the entry
```

**Prerequisites before installing:**
1. `make install` (so the launcher, venv, and `~/bin` symlinks exist).
2. (Workers that drive issues need GitHub push access) a working token in `.env`
   (gitignored) — the dispatcher reads `GITHUB_TOKEN` from it at runtime. Never
   commit the token.
3. `python3` on PATH (macOS: the helper falls back to `/opt/homebrew/bin/python3`
   if present; Linux: plain `python3`).

**What the entry does** — every 20 min it launches `scripts/watchloop_dispatch.py`
as a `project-manager` Hermes session (`cwd = this repo`, so `AGENTS.md` loads as
its rulebook) that polls PRs/CI, merges ready PRs, and drives every open issue to
a PR. See the "Self-driving development" section above.

**First-tick smoke check** after `make cron-install`:
```bash
crontab -l | grep watchloop_dispatch      # entry present
# wait up to 20 min, then confirm the loop ran:
tail .watchloop/run/dispatch.log          # should show a `tick start` line + activity
```

### Observing the watch loop (`make watch-report`)

To see whether the cron agents are actually working, run the on-demand status
report (host-side, reads the repo's own `.watchloop` logs + live GitHub state):

```bash
make watch-report            # default: last 60 dispatch.log lines
make watch-report WINDOW=200 # wider dispatcher window
```

`make watch-report` is **exercised in CI** by the `watch-report` job, which runs
the real target against a committed fixture `.watchloop` tree + a fake `gh`
shim (no real loop data, token, or network) and fails if any report section is
missing or the command errors.

It answers three questions:

1. **What work did the cron agents do?** — each worker session found in
   `.watchloop/logs` is listed with its issue, PR, branch, heartbeat count, and
   a "what this tick did" snippet when the log carries a `STATUS: DONE` /
   `WATCH-LOOP SUMMARY` block. Live workers (heartbeat within the last 40 min)
   are shown separately from STALE/DONE logs, so a leftover log from a finished
   branch is never mistaken for an active worker.
2. **What is the output rate?** — live open issues + open PRs with each PR's
   merge-state, review decision, and compact CI verdict; plus the dispatcher
   timeline (spawn / repair / merge-wait / clean / tick counts in the window)
   and a tick-start-vs-tick-done balance check that flags a possible doubled or
   incomplete run.
3. **How does it react to red CI?** — repair-stage action count in the window
   plus any open PR currently showing failing CI (the PRs the repair stage is
   expected to fix).

**Per-OS notes:**
- macOS: cron uses a minimal PATH; the entry prefixes
  `/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin`. If you use a
  custom python, `make cron-install PYTHON=/path/to/python3`.
- Linux (systemd-cron / vixie-cron): the same cron syntax applies; the entry uses
  plain `python3` from your cron PATH. If `cron` isn't running: `sudo systemctl
  enable --now cron` / `sudo service cron start`.

**To remove the loop entirely:** `make cron-uninstall`.

---

## Layout

```text
llgenie/
├── tools/             # gguf-tooling venv + pip-compile container
│   ├── Makefile
│   ├── requirements.in      # source of truth (numpy, gguf==0.19.0)
│   ├── requirements.txt     # generated by pip-compile
│   └── Dockerfile           # pip-compile resolver (python:3.10-slim)
├── containers/
│   ├── ci-variant/            # CI helper (variant build image)
│   ├── engines/               # engine container images (one per engine x arch)
│   │   ├── base/              #   shared toolchain base per backend (Dockerfile.cpu/cuda/rocm/vulkan)
│   │   ├── dockerfiles/<engine>/Dockerfile.<arch>   # generated per engine x arch
│   │   ├── entrypoint.sh      #   serve | health | detect | info | shell
│   │   └── params/<engine>.json  # generated engine params (skills -> params, committed)
│   └── test/               # test image: python+pytest+deps + hf + docker CLI
│       └── Dockerfile
├── data/
│   ├── models.json         # vendored trending-local-llms registry (make sync-registry)
│   └── trending-README.md  # the README the registry was generated with
├── docker-compose-files/  # hermetic test container (documented)
├── scripts/
│   ├── llama_serve.py      # GGUF launcher + llama-server auto-tuner + --download-top-tier / --trend / --select
│   ├── model_engine_pick.py # trend/README pick, engine ranking, GGUF download plan (no mocks)
│   ├── engine_skills.py    # engine skills: detect/install/launch every engine (no engine-specific code)
│   ├── engine_image.py     # skills -> engine params + Dockerfiles; build/push/pull images
│   ├── engine_runner.py    # run a built engine image on a host port
│   ├── engine_smoke.py     # smoke-test an engine start script (--version / "hi")
│   ├── install_engine_launchers.py  # writes ~/bin/llgenie-engine-<id> start scripts
│   ├── sync_registry.py    # vendor + validate data/models.json + trending-README.md (make sync/check)
│   ├── detect_server.py    # card RAM / backend detection (LLAMA_RAM_BYTES seam)
│   ├── native_build_env.py # macOS Metal native build env (build_llama_server.sh)
│   ├── hf_download.py      # HF downloader (auto-resume/retry, throttled, xet->HTTP fallback)
│   ├── __init__.py         # package marker for hermetic unit tests
│   ├── loop_harness.py     # `make loop` orchestrator (stages)
│   ├── lint_linefeeds.py   # linefeed/editorconfig lint (--fix)
│   ├── check_openspec_tasks.py  # validates openspec task checkboxes
│   ├── install_watchloop_cron.py / watchloop_dispatch.py / watch_report.py  # background watch loop
│   ├── serve_variant.py    # serve a built native variant on a free port
│   └── ...                 # helper scripts (see make help / AGENTS.md)
├── skills/engines/<id>/SKILL.md   # one skill per inference server (single source of truth)
├── tests/
│   ├── test_trend_pick.py            # trend pick: README list, engine ranking, real downloads
│   ├── test_engine_skills.py         # skills -> image -> version/digest tests
│   ├── test_model_engine_pick.py     # pick logic unit tests
│   ├── test_install_trend.py         # pty trend pick from installed ~/bin/llgenie
│   ├── test_install_published.py     # pty trend pick per backend from published images
│   ├── test_llama_ai.py / test_top_tier_acceptance.py / test_install.py / test_health.py
│   ├── test_watchloop_dispatch.py / test_watch_report.py / ...  # unit + e2e/watch tests
│   └── conftest.py / ptydrive.py / fixtures/   # shared test helpers
├── .github/workflows/
│   ├── ci.yml              # parallel per-stage CI (all branches/PRs)
│   └── registry-sync.yml   # daily sync-registry, opens a PR when the registry changed
├── openspec/changes/    # OpenSpec change tracking (spec-driven; proposal/spec/tasks)
├── LICENSE              # MIT
└── README.md
```

## License

MIT — see [LICENSE](LICENSE).
