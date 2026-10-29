# llgenie

Pick and serve a local LLM through an OpenAI-compatible endpoint (`llm-local`) on
`http://127.0.0.1:11434/v1`. llgenie starts from the
[trending-local-llms](https://github.com/andyholst/trending-local-llms) README list, ranks the
engines per model against *this* card, downloads the quant that fits, and serves it — llama.cpp,
Prism, vLLM, Ollama, SGLang, MLX or TensorFold, whichever the registry ranks first here.

This README is the **user guide**: what llgenie is, how to install it, how to use it, and one page
on how it works. The references it points at:

| Document | What it answers |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | how the code is laid out and how a request flows through it — the map of this repository |
| [`docs/ENGINES.md`](docs/ENGINES.md) | one inference server per engine: how each image is built, tested and published, and which llama.cpp build this card gets |
| [`docs/BOTS.md`](docs/BOTS.md) | the automation: which bot does what, its cron slot, the skills its legs run under, where secrets go, and every CI/verification target |
| [`docs/SCANNERS.md`](docs/SCANNERS.md) | the security scanners: one immutable Wolfi image per scanner (digest-pinned base, exact version, content-hash tag), how to bump one, and the gate that keeps `digests.json` true |
| [`docs/SCANS.md`](docs/SCANS.md) | the vulnerability scans: which scanner runs from which pinned image, the daily-only triggers, the failure policy, the floor the scan compiles into the pins, and the SBOM/SARIF outputs |
| [`docs/SECURITY.md`](docs/SECURITY.md) | what is pinned and how it is updated: every GitHub Action at a full commit SHA, the gate that enforces it, and the documented update path |
| [`docs/RENOVATE.md`](docs/RENOVATE.md) | what Renovate owns (Python pins, container base images), what it must never touch, its low-risk-only automerge policy, and why a base-image bump builds images |
| [`CHANGES.md`](CHANGES.md) | the change index — one row per change, each rendered from its own file in `docs/changes.d/` so two changes never edit one line, linking its dated `agent-wiki/` note |
| [`AGENTS.md`](AGENTS.md) | the workflow rules for an agent or a bot working in this repository |

A change's own record is a dated Zettelkasten note in `agent-wiki/YYYY-MM-DD-<kebab>.md`, with its
index row in `docs/changes.d/<note-name>.md` (one row per file — see below) and rendered into
`CHANGES.md`. No bot appends change history to this file (`make check-docs` fails if one does).

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
- **macOS (Metal) never starts an engine image.** Apple Silicon runs the native
  Metal engines (TensorFold, MLX, llama.cpp, Prism, Ollama, LiteRT). `make install`
  and `llgenie` do not pull or start a container image, and they never start Colima.
  A container-only engine is not offered. Linux still pulls this host's images.
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
2. **launcher** — writes an executable `~/bin/llgenie` that runs `scripts/llgenie_serve.py` **with the
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
   unless each one exits 0 and prints its engine version through its image (on any output
   line: container-runtime warnings around it are ignored).
   On cuda, the start scripts and both shims pass `--device nvidia.com/gpu=all`. If
   `/dev/nvidia-modeset` is missing (the `nvidia_modeset` module can be loaded without
   that device node), they run `nvidia-modprobe -c 0 -m -u` before `docker run` and exit
   if the node is still missing. `LLGENIE_NO_GPU=1` drops the CDI device first, so that
   path does not call `nvidia-modprobe`.
4. **symlink + smoke** — symlinks `~/bin/llgenie.py` → this repo's launcher (`scripts/llgenie_serve.py`),
   then runs `~/bin/llgenie --list`. Succeeds even when `~/models` is empty (you populate it with
   `llgenie --download-top-tier`), failing only on a genuine gguf/launch error.
5. **PATH** — if `$HOME/bin` is not already on `PATH` in the default shell's rc file,
   adds `export PATH="$HOME/bin:$PATH"` at the top of `~/.bashrc` (login shell bash)
   or `~/.zshrc` (login shell zsh). An existing line is left unchanged.

## Use it — `llgenie` picks the model and the engine

`llgenie` with no model is interactive:

1. **The trend list**: exactly the [trending-local-llms](https://github.com/andyholst/trending-local-llms)
   README "Most loved" list, in README order (🔥 trending -> 🕑 recent -> 💤 stale, then trend score),
   every model whose **stated minimum** fits this card — `vram_min` (the store's measured minimum)
   when the store states one, else the README's VRAM column — and the figure printed beside each row
   is that same one, so the list never shows a number it did not gate on (a 16 GB card is 16 GB even
   though `nvidia-smi` reports 15.99 GiB, and a model the store proves runs at 12 GB is listed under
   12GB, not under a bigger display bucket). Every model you can run here is numbered, downloaded or not
   (`[local]` = already in `~/models`); one that cannot run here stays in the list as `--` with the reason.
2. **Engines** for the chosen model, each with the format llgenie fetches for it. A figure is
   compared to **this host's card**, not just its backend: first the figures measured
   on this host's kind of hardware (RTX for cuda, Radeon/Strix Halo for rocm/vulkan, Apple Silicon
   for metal, CPU for cpu) **and on a card of this card's class or smaller** — the only figures
   proven to describe this card; then a same-backend figure measured on a **bigger card** or on
   hardware that names no card (labelled `(CUDA, 48 GB card)` / `(CUDA, card unknown)`); then
   figures from other hardware (`(ROCm)` / `(CPU)` / `(Metal)`); then a **datacenter** figure
   (`(CUDA, datacenter)`, never a fit for a card); then engines the registry lists as supported
   without a figure. On a 16 GB card that means the 108 t/s `RTX 5060 Ti 16GB` figure leads, not
   the 300 t/s one from a `2x RTX 4090` box. A card size that cannot be detected (an Apple-Silicon
   or CPU host) leaves the backend rule alone. The t/s text comes from ONE rule
   (`model_engine_pick.tps_label`), so the printed list and its tests cannot disagree.
   An engine is offered only when the model has a **downloadable plan** for it: a t/s figure says
   somebody ran the model, not that you can fetch it. The committed quant table
   (`data/trending-quant-catalog.json`) is what answers that, so a model the table does not cover
   yet is still served (it falls back to a live Hub lookup).
3. **Download** when missing, in the engine's format:
   - `gguf`: the registry's GGUF repo, else the most-downloaded `<name>-GGUF` repo; the largest GGUF
     within 80% of the card minus 1 GiB (16 GB -> 11.8 GB). MoE models add system RAM minus 4 GiB
     (llama.cpp keeps the experts in RAM). Split models: all shards. Never MTP heads, imatrix or mmproj.
     On a Mac (unified memory) the budget is 70% of RAM minus 7 GiB for every model (48 GB -> 26.6 GB).
   - `litertlm`: the generic `.litertlm` of the registry repo (not the gpu/web/vendor builds).
   - `mlx-safetensors` / `safetensors`: the whole registry repo (config + weights); for MLX also the
     model's `<name>-MLX*` conversions on the Hub (the registry often names only the base repo).
   - TensorFold: only TensorFold's own checkpoints, the largest `TensorFold/<name>-MLX-*` that fits.
4. **Serve** through `~/bin/llgenie-engine-<id>` (image pulled on first use) on
   `127.0.0.1:<port>/v1` as `llm-local`.

**On an Apple-Silicon Mac** the list is a `metal` list. TensorFold, MLX,
llama.cpp, Prism, Ollama and LiteRT run **natively**, shown as `[metal]`, because Metal
cannot run in a container. **Picking a Metal engine makes it ready by itself, installed or
not:** missing → llgenie runs the skill's install script (the MLX wheels ship their Metal
kernels precompiled); installed at another version than the skill pins → it updates to the pin;
at the pin → it is reused. TensorFold 1.1.6 has no pip package: its release ships native
archives, so the bump rewrites the install to download/checksum/unpack into `{prefix}/{version}`
and point `{prefix}/current` at it, making the binary `{prefix}/current/bin/{id}` — the
installed version is still detected truthfully. The engine list says which:
`(installs 1.1.6 on pick)`,
`(installed 0.6.4 -> updates to 1.1.6 on pick)` or `(installed 1.1.6)`. Then llgenie
downloads the model's TensorFold checkpoint if missing, writes a native
`~/bin/llgenie-engine-<id>` (no docker) and serves. TensorFold gets a **65,536-token window**
(`--context`, the 64K Hermes Agent needs for tool use; `LLGENIE_CONTEXT=<n>` overrides, `0`
lets TensorFold size it to its budget; a Mac too small for 65,536 tokens gets TensorFold's
"does not fit ... the most one request can use is N tokens" refusal, then serve with
`LLGENIE_CONTEXT=0`) and the Mac's full GPU working set as its budget
(`TENSORFOLD_MEMORY_LIMIT_GB`): its default 70% gives a 48 GB Mac only 29,696 tokens. Point a
client at `http://127.0.0.1:11434/v1`, model `llm-local`, context length 65536. A
container-only engine is not offered on a Mac (macOS never starts an engine image),
and cuda/rocm-only engines (Strata, SGLang, ...) are not offered either. The TensorFold
*image* is CUDA-only and built by the Linux CI. A Linux container
cannot reach the Apple GPU, so no Metal image exists. Qwen3.8-Flash-Next 125B needs
≥ 63 GB of TensorFold weights: on a 48 GB Mac it is listed with that reason, and on a
128 GB Mac it is pick 1 on TensorFold.

The list is tested without the prompt (`llgenie --trend` prints exactly the rows the
prompt asks from): `tests/test_mac_trend_pick.py` (Mac),
`tests/test_trend_list_acceptance.py` (acceptance criteria AC1–AC8 on linux
cuda/rocm/vulkan/cpu and mac metal) and `tests/test_tensorfold_seamless.py`
(install / update / reuse on pick), all in `make test-unit`. That seam is **install-kind
agnostic**: it drives the kind the skill declares — a synthesized pip skill and a
synthesized release-archive skill — so a bump that moves TensorFold from a pip package to its
native archives does not redden the very lane that proves the archive shape. On an Apple-Silicon Mac,
`make test-native-engine` runs the REAL TensorFold install script through the pick
(missing → install, older → update, current → reuse; isolated uv tool dir; there is no CI
job for it, GitHub's macOS runners have no usable Metal GPU), and `make test-native-engine-serve` adds the real
`llgenie --select 1 --engine tensorfold` download of Qwen3.8-27B's TensorFold checkpoint +
Metal serve with `context: 65536` + "hi". `make test-native-engine-light` serves the lightest
model TensorFold runs (`mlx-community/Qwen3.5-9B-MLX-4bit`, 5.5 GiB) through the llgenie start
script on Metal; on GitHub's 7 GB `macos-15` runner TensorFold's own budget check refuses it
instead (smaller Qwen3.5 sizes tie their embeddings, which TensorFold 1.1.6 refuses).

Without a terminal:

```bash
llgenie --trend                 # print the numbered list and exit
llgenie --select 4              # take row 4: download it if missing, serve with its top engine
llgenie --select 2 --engine llama.cpp --dry   # row 2 on llama.cpp; --dry = print the plan only
llgenie --matrix                # print EVERY model x engine x quant permutation that fits
                                 #   this card (VRAM) + RAM, each with its exact
                                 #   https://huggingface.co/.../resolve/... URL (no download/serve)
llgenie --matrix 24 32          # same, for a mocked 24 GB VRAM / 32 GB RAM host
llgenie --matrix 24 32 cuda     # same, for a CUDA host (also: rocm | vulkan | metal | cpu)
llgenie --matrix --vram 24 --ram 32 --arch cuda   # explicit flags — the clearest form
```

The explicit flags are the recommended, unambiguous way to drive the matrix:
`--vram V` (GPU VRAM, GB), `--ram R` (system RAM, GB), `--arch A`
(`cuda | rocm | vulkan | metal | cpu`). They take precedence over the positionals
`[GB] [RAM_GB] [ARCH]`, which in turn override the detected host. CI varies the
whole (arch × vram × ram) permutation set through these: the choice of inference
**server is selected by the architecture** — only engines with a runnable image
variant for that host are offered (the arch variant, else the cpu fallback image;
on Metal never a cpu image, issue #120) — and each chosen (model, engine) maps to a
resolvable HF quant URL. The env seams `LLGENIE_BACKEND` / `LLGENIE_RAM_BYTES` /
`LLGENIE_SYSTEM_RAM_BYTES` do the same when neither flags nor positionals are given.
`tests/test_pick_matrix_arch_perms.py` asserts the whole (arch × vram × ram)
permutation set on the Linux CI (`make test-unit`), and `tests/test_pick_full_registry.py`
is the **system pick-matrix test**: it exercises the whole llgenie business logic for
REAL over `data/models.json` — every trending model × every engine × arch × vram × ram —
against the live Hugging Face Hub (the real quantized files and their real
`https://huggingface.co/<repo>/resolve/<rev>/<file>` links are the source of truth, each
asserted HTTP 200), with the ONLY thing mocked being the inference server start. A
use-case pass runs the real `llgenie --pick <model> --engine <engine> --dry` launcher
for every registered (model × engine × arch): `--dry` prints the plan and returns BEFORE
the start script runs, so the whole pick runs end-to-end without starting any inference
server (the engine start is mocked), asserting the CLI agrees with `matrix()`. The
interactive pick's "model → its supported engines → the quants THAT engine supports →
take the highest that fits" is first-class business logic:
`mp.engine_supported_quants(model, engine, gb, ram_gb, arch)` (ascending real quants of
the engine's own format) + `mp.pick_quant(...)` (the highest that fits), both covered by
`tests/test_engine_supported_quants.py`. The pick logic reads it from a committed HF
class table `data/trending-quant-catalog.json` (model → engine → `{arch, quants}`, each
quant a real resolvable `huggingface.co/.../resolve/...` plan), so deciding what a chosen
engine can load on this hardware never re-queries the live Hub (the pick's comparison
path is hermetic; the Hub is touched only when downloading). `tests/test_trending_quant_catalog.py`
asserts the table is well-formed and its committed fixture
(`tests/fixtures/trending-quant-catalog.json`) exactly matches it — a link change or a
dropped section is a caught regression — and the system pick-matrix test asserts every
pick is a real catalog link. Nothing in the suite downloads a model — it only checks
links exist, and it does that through **ONE shared probe** (`tests/hub_probe.py`, issue #256): a
ranged GET that retries the Hub's transient set (429, 500/502/503/504, a stalled connection) on a
bounded 1+2+4+8 s ladder and returns the status it saw, so a transient gateway error no longer
reddens the lane as "real file missing (HTTP)" — a definitive answer (HTTP 404) is still one
request and still fails. Once three probes have exhausted the budget the Hub counts as degraded
(one attempt per link) so a sustained outage cannot multiply 15 s across the thousands of links
these suites verify; every unverified link still fails, loudly. `tests/test_hub_probe.py` locks
the retry, the ladder, the no-retry-on-404 rule and the breaker against a real loopback server.
The **golden edge-case suite** (`test_pick_matrix_edge_case_golden`, 525
cases, + `test_pick_matrix_edge_case_golden_ram`, 17) asserts every trending model ×
engine × arch × VRAM ladder (8/16/24/32/64) and the RAM-sensitive engines' RAM ladder
(16/32/48/60/64) as explicit `(arch, model, engine, vram, ram) -> expected quant`
cases through the REAL `llgenie --matrix` CLI. RAM-sensitive engines covered: **Strata**
(Q2_0 below 60 GB RAM, IQ3_XXS from 60 GB up) and **FreeToken** (MoE: more RAM → larger
quant). No gaps across model × engine × arch × VRAM × RAM.

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

The registry is `data/models.json` (with the README it was generated with, `data/trending-README.md`), a copy of
[trending-local-llms](https://github.com/andyholst/trending-local-llms) `data/models.json`
(no live fetch at run time; `LLGENIE_REGISTRY_SRC=<file|url>` overrides it). The contract that store is
written against is vendored beside it — `data/model_contract.json` (the JSON Schema upstream validates
`models.json` with) and its prose twin `data/MODEL_CONTRACT.md` — so an upstream contract edit arrives as
a diff of the contract, and `make check-registry` validates the store against the rules read **from that
schema** (required keys per model row, `formats[].name`/`hf`, the `id` pattern, an engine's `backend`
enum) instead of a hand-kept key list.

Each model also states **what its run needs**, per upstream's `data/MODEL_CONTRACT.md`:

| field | llgenie reads it as |
|---|---|
| `weight_gb` | the weight budget *before* any context is allocated (`5.95GB Q4_K_M` → 5.95 GB); preferred over a Hub file-size guess in the "does not fit" reason |
| `context_tokens` | the window the KV cache is sized for (`131072`, `128K`, `1M`) |
| `system_ram_min` | a hard floor: a host below it does not fit, however much VRAM it has |
| `storage_offload` | the model runs by streaming weights from storage (MoE); named in the reason |
| `engine_min_version` | the engine build / flags the figure needs, carried on the engine row |

They may sit on the model **or** on one `engines[]` measurement ("the footprint of that run"); the
measurement's own value wins for that engine, and a field the store does not state is a reported data
gap — never invented. `weight_gb`, `context_tokens` and `system_ram_min` are **grow-only** in
`make check-registry-keys`: they are static data about a run, and a lower value shrinks the budget
llgenie allocates.

**What the additive-only gate fails on, and what it only reports.** Upstream rewrites its
rows on every refresh, so the guard compares *identity*, not text. It **fails** the sync when a model row
is gone, a key is gone from a model row, an engine that had a measurement for a model has none, a
`backends` / `supported_engines` entry is gone, a **format** (`GGUF`, `MLX`, …) is gone — a non-format
display name in `formats` is upstream text, not data, so the normaliser may drop it — an engine-registry entry is gone, a
stated footprint is lowered, or a **tracked post** (the `/status/<id>` of a `source_post`) is nowhere in
the new store. It **prints as a `NOTE:`** (and exits 0) when a surviving post's t/s is re-stated lower, an
engagement counter drops (X re-scrapes move likes/views both ways), or the derived `engagement.seen_posts`
placeholder shrinks. A measurement is identified by its post store-wide, so a refined hardware string, a
post re-attributed to a split model row, and a profile link upgraded to its real status URL are the same
measurement — keying on `(engine, hardware)` read all of them as a loss and froze the weekly sync for 13
days.

```bash
make sync-registry    # download upstream data/models.json + README.md + data/model_contract.json
                      # (+ MODEL_CONTRACT.md) into data/ (validated: the store must satisfy that
                      # contract and be the README "Most loved" list in README order)
make check-registry   # validate the vendored store against the vendored contract, its README order
                      # and its live links (CI)
make check-registry-keys  # CI: additive only — a removed model/key/engine/format/tracked post or a
                      # lowered weight_gb/context_tokens/system_ram_min fails the sync; a re-stated
                      # t/s or re-scraped counter is printed as a NOTE and does not
make sync-quant-catalog   # regenerate the HF class table data/trending-quant-catalog.json + its test
                          # fixture (model -> engine -> arch + real quant plans with per-quant links)
                          # from the registry + live Hub; validates the newly-added links vs the prior table
make check-quant-catalog  # CI: fail if the committed quant catalog differs from the generator's output
                          # "differs" = a row the committed table HAS is no longer generated (a plan
                          # gone, a plan whose repo/files/size/link changed, an engine's arch list
                          # changed, or a table rendered for another registry). What the LIVE Hub
                          # re-reads is printed as a NOTE and does not fail: the table is regenerated
                          # from a `sort=downloads` search, so the same plans come back in a different
                          # order as those counts move, and a conversion upstream publishes shows up as
                          # an extra row — recording both is `make sync-quant-catalog`'s job.
                          # A NEWLY-generated link is probed on the live Hub: readable (200/206) is fine,
                          # GATED (401/403 — the file exists, the token may not read it) is reported as
                          # `gated=N` and does not fail the sync, and only a DEAD link (404/410, 5xx, a
                          # failed read) reds it
make render-trend-list-matrix  # rewrite tests/fixtures/trend-list-matrix.json: the trending
                              # list for every arch x vram x ram, from `llgenie --matrix`
make check-trend-list-matrix   # CI: fail if that file differs from a fresh matrix() call
make registry-change-report    # print what the working-tree store changed vs HEAD: added/removed/
                               # renamed models, new engines, contract keys, README rows, table counts
make sync-change-issue         # open ONE issue stating that change (the weekly sync runs it; it
                               # updates that issue in place for the same generated_utc, DRY=1 previews)
make render-engine-skill-gap   # rewrite data/engine-skill-gap.json: the per-engine list (status,
                               # image variants, the models each engine is the top engine for,
                               # per arch) + the models no engine can offer
make check-engine-skill-gap    # CI gate: fail on a registry engine with no skill and no dated
                               # decision, a stale decision, or a stale rendered file
make engine-skill-gap          # show that gap (shipped / known-unsupported / NEW-unresolved)
make engine-skill-gap-md       # the same gap as MARKDOWN, for a PR/issue body (the registry-sync
                               # workflow embeds it, so the step calls a make target - issue #296)
make check-engine-coverage      # CI gate: fail when a shipped servable engine has no buildable CI
                               # image cell (a cell in DISABLED, a variant outside cpu|cuda|rocm|vulkan,
                               # or no linux image) and no recorded exception (issue #771)
make engine-coverage-report     # every shipped engine -> built | not-an-image | unbuilt, with the
                               # reason; a KNOWN_UNBUILT entry that is now built fails as stale
make spawn-engine-skill-issues # open one tracking issue per NEW unskilled engine (the sync does this),
                               # labelled `agent:implement` and read back — an unlabelled issue routes to
                               # no bot, so the label is applied explicitly and verified (issue #724)
make engine-skill-scaffold ENGINE="<registry name>"  # write skills/engines/<id>/SKILL.md from the
                               # registry's own entry (engine, repo, backends) plus the `os:` those
                               # backends can run on — a Metal-only engine is `darwin`, because Metal
                               # runs natively and never in an image; every key it cannot
                               # prove is left EMPTY so `make skills-validate` names it (ID= overrides
                               # the kebab, BACKENDS= when the registry names none, OUT=/REGISTRY= pick
                               # another tree/store, DRY=1 previews, FORCE=1 overwrites a skill)
make check-wiring              # CI: fail when a test/script is wired to no make target, or only to
                               # one CI never runs (tests/fixtures/host-only-wiring.json records the
                               # deliberate ones), a workflow calls a make target that does not exist,
                               # a target is not declared .PHONY, or a .PHONY entry names a target that
                               # cannot run (no target at all, or no recipe and no prerequisite — `make
                               # <name>` then prints "Nothing to be done" and exits 0; issue #883)
make wiring-report            # show how every test/script is wired (which target, whether CI runs it)
```

Every check needs exactly one `make` path, and CI must be the one that runs it — so the
wiring is itself checked: a new `tests/test_*.py` nobody names, a `scripts/*.py` nothing
references or imports, or a `make <target>` typo in a workflow `run:` block fails
`make check-wiring` (a step of `ci-unit`) and names what to fix. The same gate covers the
Makefile's own promises: a target whose `##` comment claims CI coverage (a CI job, pipeline,
matrix or runner) that no CI job reaches is an error, or a recorded, dated entry in
`tests/fixtures/host-only-wiring.json` (`targets`) — that is how `make test-install-ci` and `make ci-engine-images` are on the record instead of being believed. A check that
can only run by hand — a native-Metal engine, the installed launcher on real hardware — is
recorded the same way (with the target a human runs); the moment CI reaches it, the entry is
stale and the gate says to delete it. The same check covers the code inside those scripts:
a top-level definition whose name appears exactly once in the tree is its own `def` line and
nothing else — dead — so a helper that loses its last caller is named instead of sitting
there.

### Manual setup (only if you don't want `make install`)

```bash
# 1. venv

cd tools && make venv-install      # create ~/llama-gguf-tools/.venv + install deps
# 2. run with the venv python

~/llama-gguf-tools/.venv/bin/python scripts/llgenie_serve.py --list
```

`requirements.in` is the single source of truth; `requirements.txt` is generated with
`pip-compile` inside the `tools/` Dockerfile container (`make generate-requirements`).

## Download a model (`scripts/hf_download.py`)

```bash
python3 scripts/hf_download.py <repo_id> <filename> <dest_dir> <label>
python3 scripts/hf_download.py <repo_id> -          <dest_dir> <label>   # whole-repo snapshot
```

- Every Hub call (API, resolve, the `hf` CLI, and engine containers) sends `HF_TOKEN` from the environment, or from `~/.zshrc` / `~/.bashrc` when the environment is empty. CI sets that environment from the `HF_TOKEN` Actions secret (`secrets: inherit` into `pipeline.yml` and `published.yml`). The token is never stored in the repo. API GETs prefer IPv4 and retry a timed-out read with a new request; a transport failure is not remembered as an empty file tree. A **read-phase** timeout is the builtin `TimeoutError`, not a `URLError` (it is raised inside `http.client`/`ssl` once the connection exists), so both Hub GET seams — `hf_auth.hub_open` and the top-tier discovery's `_hf_get` in `scripts/llgenie_serve.py` — name both classes and retry it on their own budget; a single stalled read no longer kills the family dry run with a traceback. A Hub 429 waits out the rate-limit window through `scripts/hf_auth.py` (`rate_limit_wait`: the `RateLimit` header's `t`, else 5 minutes, capped at 10) and is retried twice; a later success resets that count. The size lookup, the ranged chunk download and the preflight probe open the Hub through `hub_open` in that same module, so a download waits out the same window instead of calling `urlopen` itself. That seam now carries the WHOLE transient set — 429 as above, 500/502/503/504 and transport failures on a doubling ladder bounded by `HUB_MAX_ATTEMPTS` — and raises on the first answer for every other status; `scripts/model_engine_pick.py` opens its API URLs through it too (its IPv4 preference passed as the `opener`), and a transient answer there is "unknown", **not** a cached empty repository.
- `-` in place of the filename fetches the **whole repo** (config.json + safetensors, an MLX/safetensors model) into the destination — same CLI, same fast path, resume and retry rules, so a caller never needs a second downloader.
- When an attempt fails while the Hub is rate-limiting it, the retry waits the seconds the Hub's own answer names (`429 Too Many Requests ... Retry after N seconds`, via `scripts/hf_auth.py::throttle_wait`; no number → the 5-minute window, capped at 10) instead of the fixed short pause. The engine images' smoke stage fetches its tiny model through this downloader for exactly that reason.
- Sets `HF_HUB_ENABLE_HF_TRANSFER=1 HF_HUB_DISABLE_XET=1` for speed.
- Auto-retries (up to 20 attempts), resuming the partial file on dropped connections.
- Appends a `.progress.log` next to the destination for live monitoring.

**Example:**

```bash
python3 scripts/hf_download.py Qwen/Qwen3.5-24B-GGUF qwen3.5-24b-q5_k_m.gguf ~/models/Qwen/24GB qwen-q5
```

## Launch or serve a model (`scripts/llgenie_serve.py`)

Run with the tooling venv's Python so `gguf`/`numpy` are importable:

```bash
~/llama-gguf-tools/.venv/bin/python scripts/llgenie_serve.py --list     # list models, don't run
~/llama-gguf-tools/.venv/bin/python scripts/llgenie_serve.py <name>     # run by substring
~/llama-gguf-tools/.venv/bin/python scripts/llgenie_serve.py            # interactive picker
~/llama-gguf-tools/.venv/bin/python scripts/llgenie_serve.py --dry qwen # print the command, don't run
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
of `scripts/llgenie_serve.py`. For `--download-top-tier`, the fit is **dynamic**: the total
comes from the actual card (`LLGENIE_RAM_BYTES` overrides it), headroom is capped at 45% of
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
  (`sysctl hw.memsize` on macOS, `/proc/meminfo` on Linux, or `LLGENIE_RAM_BYTES`), with
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

LLGENIE_RAM_BYTES=$((8*1024**3)) llgenie --download-top-tier --family qwen --count 1 --dry
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
  (HTTP 429/500/502/503/504 and plain network / socket-timeout errors). A 429
  waits for the Hub's fixed 5-minute window to reset: the `t` seconds from the
  `RateLimit` header, or 5 minutes when the header has no `t`, and never more
  than 10 minutes (`scripts/hf_auth.py` `rate_limit_wait` — the one wait every
  Hub caller and its tests use). Every CI process that runs the launcher or the
  real downloader against the Hub allows that 10-minute cap plus 180 seconds
  (`TOP_TIER_DRY_RUN_TIMEOUT`), so one sleep cannot expire the process before
  the retry finishes. It is retried twice; any response that is not
  a 429 resets that count. A **permanent** error
  (401/403/404) is never retried — it fails fast so a genuinely gated/dead repo is
  still reported loudly (the skip+refill and "no repos" paths above). Without this
  retry, a single 429 on one repo tree would silently drop that repo and turn a
  valid match into a false "no model fits".

Without `--family` the command behaves byte-identically to before (all existing
top-tier tests pass unmodified).

## How it works

One pipeline, four steps, no magic:

1. **Registry** — `data/models.json` is a weekly copy of
   [trending-local-llms](https://github.com/andyholst/trending-local-llms): models, their VRAM
   column, per-engine throughput measurements and the engagement counters behind the trend score.
2. **Rank** — the trend list that fits this card; then, per model, the engines ranked by a
   measurement that describes *this* card (same hardware class, card size or smaller), with the
   fallback order documented in "Use it" above.
3. **Fetch** — the quant in that engine's format, sized to the card's memory budget.
4. **Serve** — the engine's image (or the native Metal install on an Apple-Silicon Mac) behind
   `llm-local` on `127.0.0.1:11434/v1`.

Each engine is a skill ([`skills/engines/<id>/SKILL.md`](skills/engines)) that states its pin,
install steps, apt packages and launch flags; `make generate-engine-params` freezes those into
per-arch Dockerfiles and params. **The code map — which script owns which step, how the modules
import each other, every gate — is [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)**; the engine
build/test/publish detail is [`docs/ENGINES.md`](docs/ENGINES.md); the automation is
[`docs/BOTS.md`](docs/BOTS.md).

## Working in this repository

An agent or a maintainer drives the same make targets the pipeline does:

```bash
make worktree-prune DRY=1     # list the worktrees + branches whose PR is MERGED and landed
make worktree-prune           # remove those (never a hand-typed `git branch -D`)
make rebase-bot-abort         # abort a stopped rebase and leave the tree on main
make verify-closure PR=<n>    # prove a merged PR's `closes #<n>` actually closed its issue
make auto-merge-explain PR=<n>  # why the merge job would (not) land this PR
```

The rules an agent follows here (branch, PR body, commit authorship, review replies) are in
[`AGENTS.md`](AGENTS.md); the bots that act on them are in [`docs/BOTS.md`](docs/BOTS.md).

## Documentation and its gates

This README is the user guide. The references it links are checked, not trusted:

```bash
make docs-report            # every user-facing make target, where it is documented, and each
                            # change note's own index row
make check-docs             # CI gate: an undocumented target, a stale decision, a change note with
                            # no index row, a row naming a missing note, or change history appended
                            # to this README fails it
make changes-index           # re-render CHANGES.md from docs/changes.d/ (the rows are one file each)
make changes-index-report    # the fragment census, and how many rows CHANGES.md is behind
```

A change's history is a dated note in `agent-wiki/YYYY-MM-DD-<kebab>.md`, indexed by a row in
`docs/changes.d/YYYY-MM-DD-<kebab>.md` — one row per file, so two changes in flight never edit the
same line and no merge can re-dirty an open PR (issue #934). [`CHANGES.md`](CHANGES.md) is that
index rendered into one table; `make changes-index` writes it and no change PR edits it by hand.
The history is never a section of this file. `make check-dispatch-forms` verifies the
generated dispatch table in [`docs/BOTS.md`](docs/BOTS.md) against the workflows themselves, and
`make check-workflows` validates every workflow file.

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
│   ├── model_contract.json # the JSON Schema models.json must satisfy (vendored with it)
│   ├── MODEL_CONTRACT.md   # that contract's prose twin (vendored with it)
│   ├── trending-README.md  # the README the registry was generated with
│   ├── trending-quant-catalog.json  # HF class table llgenie's pick reads (make sync-quant-catalog)
│   └── strata_models.json  # Strata's setup.py model/file/shard map (make sync-strata-models)
├── docker-compose-files/  # hermetic test container (documented)
├── scripts/
│   ├── llgenie_serve.py      # GGUF launcher + llama-server auto-tuner + --download-top-tier / --trend / --select / --matrix
│   ├── model_engine_pick.py # trend/README pick, engine ranking, GGUF download plan (no mocks)
│   ├── engine_skills.py    # engine skills: detect/install/launch every engine (no engine-specific code)
│   ├── engine_image.py     # skills -> engine params + Dockerfiles; build/push/pull images
│   ├── engine_runner.py    # run a built engine image on a host port
│   ├── engine_smoke.py     # smoke-test an engine start script (--version / "hi")
│   ├── install_engine_launchers.py  # writes ~/bin/llgenie-engine-<id> start scripts
│   ├── sync_registry.py    # vendor + validate data/models.json + trending-README.md (make sync/check)
│   ├── gen_trending_quant_catalog.py  # HF class table generator: model -> engine -> arch + real quant plans (make sync/check-quant-catalog)
│   ├── detect_server.py    # card RAM / backend detection (LLGENIE_RAM_BYTES seam)
│   ├── native_build_env.py # macOS Metal native build env (build_llama_server.sh)
│   ├── hf_download.py      # HF downloader (auto-resume/retry, throttled, xet->HTTP fallback)
│   ├── __init__.py         # package marker for hermetic unit tests
│   ├── loop_harness.py     # `make loop` orchestrator (stages)
│   ├── lint_linefeeds.py   # linefeed/editorconfig lint (--fix)
│   ├── check_openspec_tasks.py  # validates openspec task checkboxes
│   ├── serve_variant.py    # serve a built native variant on a free port
│   └── ...                 # helper scripts (see make help / AGENTS.md)
├── skills/engines/<id>/SKILL.md   # one skill per inference server (single source of truth)
├── tests/
│   ├── test_trend_pick.py            # trend pick: README list, engine ranking, real downloads
│   ├── test_engine_skills.py         # skills -> image -> version/digest tests
│   ├── test_model_engine_pick.py     # pick logic unit tests
│   ├── test_install_trend.py         # pty trend pick from installed ~/bin/llgenie
│   ├── test_install_published.py     # pty trend pick per backend from published images
│   ├── test_llgenie_serve.py / test_top_tier_acceptance.py / test_install.py / test_health.py
│   └── conftest.py / ptydrive.py / fixtures/   # shared test helpers
├── .github/workflows/
│   ├── ci.yml              # parallel per-stage CI (PRs to main + pushes to main)
│   ├── registry-sync.yml   # weekly sync-registry + quant catalog (cron 19 5 * * 1), opens a PR when changed
│   ├── engine-bump.yml     # weekly engine pin bumps (cron 53 6 * * 1, separate), opens a PR per changed engine
│   └── engine-bump-rebase.yml  # daily: rebase open engine-bump PRs onto the latest main
├── openspec/changes/    # OpenSpec change tracking (spec-driven; proposal/spec/tasks)
├── LICENSE              # MIT
└── README.md
```

## License

MIT — see [LICENSE](LICENSE).

## Environment variables

- `LLGENIE_KV_QUANT` — the KV cache type a llama.cpp launch serves: a type name from the
  table (`f16`, `q8_0`/`int8`, `k8v4`, `q5_0`, `q4_0`, …) or `auto` for the largest that
  still fits this card and context. Unset keeps `q4_0`, the tightest cache, and an
  unknown name fails loudly instead of silently falling back. The resolved
  value is the one used by the context budget, the GPU-layer count, `-ctk`/`-ctv` and the
  plan printed by `--dry`.

- Publishing the agent image is `make publish-agent-image`, run by `publish-agent-image.yml`
  (`workflow_dispatch` only, behind the owner/collaborator guard, issue #222/#238/#248). The image
  is published under a **content hash** of its Dockerfile + install script + the test image it
  builds FROM. A re-run does not rebuild when that hash is already on GHCR, and it still points
  `:latest` at the hash. `make agent-image`, `make agent-image-pull` and `make agent-image-ref`
  use that `:latest` tag; the job logs in to GHCR with the **owner PAT**
  (`secrets.BUMP_TOKEN`), not `GITHUB_TOKEN`, and prints the published ref with `make
  ci-image-refs`. The credential reasoning is stated in that workflow's header, which is the file
  that has to stay true.
  Before that build the job runs `make agent-image-push-check`: it asks GHCR for a **push-scoped
  token** and then initiates an **empty blob upload** against the package the publish writes — the
  cheapest real write there is, which sends no data, so a refusal costs nothing and a success leaves
  no layer. A credential that may not publish fails in seconds, quoting the registry's own message,
  instead of after a build that could never succeed. It needs the same credential the
  login uses (`GHCR_TOKEN`), so the step passes the owner PAT.
