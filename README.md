# llgenie

Tooling to pick and serve local LLMs through an OpenAI-compatible endpoint (`llm-local`).
On Linux every inference server (llama.cpp, Prism, vLLM, Ollama, ...) runs from its
CI-tested container image pulled from GHCR (`cpu | cuda | rocm | vulkan`); on macOS Metal,
llama.cpp is built natively. Also included: a resilient Hugging Face downloader and the
Python venv scaffold the launcher needs.

This repo bundles three pieces that were built and validated together:

| Piece | File | What it does |
|---|---|---|
| **GGUF launcher + auto-tuner** | `scripts/llgenie_serve.py` | Scan `~/models/**/*.gguf`, pick a model (and engine, `--pick`), auto-tune `llama-server` flags to the detected card RAM, and serve an OpenAI-compatible endpoint at `127.0.0.1:11434`. |
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

### `llgenie`: trending model + fastest engine (issue #105)

`llgenie` with no model is interactive:

1. **The trend list**: exactly the [trending-local-llms](https://github.com/andyholst/trending-local-llms)
   README "Most loved" list, in README order (🔥 trending -> 🕑 recent -> 💤 stale, then trend score),
   every model whose README VRAM column fits this card (a 16 GB card is 16 GB even though
   `nvidia-smi` reports 15.99 GiB). Every model you can run here is numbered, downloaded or not
   (`[local]` = already in `~/models`); one that cannot run here stays in the list as `--` with the reason.
2. **Engines** for the chosen model, each with the format llgenie fetches for it: figures
   measured on this host's kind of hardware first (RTX for cuda, Radeon/Strix Halo for rocm/vulkan,
   Apple Silicon for metal, CPU for cpu), then figures from other hardware labelled
   `(CUDA)` / `(ROCm)` / `(CPU)` / `(Metal)`, then engines the registry lists as supported without a figure.
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

**On an Apple-Silicon Mac (issue #114)** the list is a `metal` list. TensorFold, MLX,
llama.cpp, Prism, Ollama and LiteRT run **natively**, shown as `[metal]`, because Metal
cannot run in a container. **Picking a Metal engine makes it ready by itself, installed or
not:** missing → llgenie runs the skill's install script (TensorFold: `uv tool install
--force 'tensorfold @ git+…@v<pinned>'`; the MLX wheels ship their Metal kernels
precompiled); installed at another version than the skill pins → it updates to the pin;
at the pin → it is reused. The engine list says which: `(installs 0.6.5 on pick)`,
`(installed 0.6.4 -> updates to 0.6.5 on pick)` or `(installed 0.6.5)`. Then llgenie
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
(install / update / reuse on pick), all in `make test-unit`. On an Apple-Silicon Mac,
`make test-native-engine` runs the REAL TensorFold install script through the pick
(missing → install, older → update, current → reuse; isolated uv tool dir; there is no CI
job for it, GitHub's macOS runners have no usable Metal GPU), and `make test-native-engine-serve` adds the real
`llgenie --select 1 --engine tensorfold` download of Qwen3.8-27B's TensorFold checkpoint +
Metal serve with `context: 65536` + "hi". `make test-native-engine-light` serves the lightest
model TensorFold runs (`mlx-community/Qwen3.5-9B-MLX-4bit`, 5.5 GiB) through the llgenie start
script on Metal; on GitHub's 7 GB `macos-15` runner TensorFold's own budget check refuses it
instead (smaller Qwen3.5 sizes tie their embeddings, which TensorFold 0.6.5 refuses).

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
links exist. The **golden edge-case suite** (`test_pick_matrix_edge_case_golden`, 525
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

The registry is `data/models.json` (with the README it was generated with, `data/trending-README.md`), a verbatim copy of
[trending-local-llms](https://github.com/andyholst/trending-local-llms) `data/models.json`
(no live fetch at run time; `LLGENIE_REGISTRY_SRC=<file|url>` overrides it):

```bash
make sync-registry    # download upstream data/models.json + README.md into data/ (validated: the
                      # registry must be the README "Most loved" list in README order)
make check-registry   # validate the vendored files (CI)
make sync-quant-catalog   # regenerate the HF class table data/trending-quant-catalog.json + its test
                          # fixture (model -> engine -> arch + real quant plans with per-quant links)
                          # from the registry + live Hub; validates the newly-added links vs the prior table
make check-quant-catalog  # CI: fail if the committed quant catalog differs from the generator's output
make render-trend-list-matrix  # rewrite tests/fixtures/trend-list-matrix.json: the trending
                              # list for every arch x vram x ram, from `llgenie --matrix`
make check-trend-list-matrix   # CI: fail if that file differs from a fresh matrix() call
make render-engine-skill-gap   # rewrite data/engine-skill-gap.json: the per-engine list (status,
                               # image variants, the models each engine is the top engine for,
                               # per arch) + the models no engine can offer
make check-engine-skill-gap    # CI gate: fail on a registry engine with no skill and no dated
                               # decision, a stale decision, or a stale rendered file
make engine-skill-gap          # show that gap (shipped / known-unsupported / NEW-unresolved)
make spawn-engine-skill-issues # open one tracking issue per NEW unskilled engine (the sync does this)
make check-wiring              # CI: fail when a test/script is wired to no make target, or only to
                               # one CI never runs (tests/fixtures/host-only-wiring.json records the
                               # deliberate ones), or a workflow calls a make target that does not exist
make wiring-report            # show how every test/script is wired (which target, whether CI runs it)
```

Every check needs exactly one `make` path, and CI must be the one that runs it — so the
wiring is itself checked: a new `tests/test_*.py` nobody names, a `scripts/*.py` nothing
references or imports, or a `make <target>` typo in a workflow `run:` block fails
`make check-wiring` (a step of `ci-unit`) and names what to fix. The same gate covers the
Makefile's own promises: a target whose `##` comment claims CI coverage (a CI job, pipeline,
matrix or runner) that no CI job reaches is an error, or a recorded, dated entry in
`tests/fixtures/host-only-wiring.json` (`targets`) — that is how `make test-install-ci`
(#239) and `make ci-engine-images` are on the record instead of being believed. A check that
can only run by hand — a native-Metal engine, the installed launcher on real hardware — is
recorded the same way (with the target a human runs); the moment CI reaches it, the entry is
stale and the gate says to delete it. The same check covers the code inside those scripts:
a top-level definition whose name appears exactly once in the tree is its own `def` line and
nothing else — dead — so a helper that loses its last caller is named instead of sitting
there.


The `registry-sync` workflow runs `make sync-registry` weekly (cron `17 5 * * 1`,
Monday 05:17 UTC), regenerates the quant catalog (`make sync-quant-catalog`), the
trend-list matrix (`make render-trend-list-matrix`) and the per-engine gap
(`make render-engine-skill-gap`), and opens a PR when any of those files changed.
The matrix fixture is the review of the new list: one block per architecture, card
size, and RAM size, in README order, with the server `llgenie --matrix` would put
first. A sync that updates `data/models.json` and leaves the fixture stale fails
`make test-unit`.

An upstream engine with no llgenie skill is left out of the startup list (no
image). That omission has to be a **decision**: `data/unsupported-engines.json`
records, per engine, `decision` (`not-shipped` | `deferred`), the `decided` date,
a `reason` and the tracking `issue` — 8 engines are recorded today
(`make engine-skill-gap` prints them, `make render-engine-skill-gap` writes the
per-engine view into `data/engine-skill-gap.json`). An engine upstream adds with
no skill and no entry is **new and unresolved**: `make check-engine-skill-gap`
fails naming it, and the sync opens one tracking issue per new engine, so the gap
is a linkable work item instead of a log line. `data/engine-skill-gap.json` also
names the models no engine can offer at all, so a model cannot vanish from the
list unnoticed. `make skills-validate REGISTRY=data/models.json
UNSUPPORTED=data/unsupported-engines.json` tolerates the recorded decisions per
engine and still fails on an undecided one. The
`engine-bump` workflow runs on its **own** cron (weekly,
Monday `23 6 * * 1`, separate from the registry sync) and pins every engine skill
to the latest upstream commit, opening a PR per changed engine (issue #107):

```bash
make engine-bump-plan [ENGINE=<id>]   # which engines moved upstream (git ls-remote only)
make engine-derive ENGINE=<id> [SHA=] # derive build params from the upstream tree (no LLM)
make engine-bump ENGINE=<id>          # pin + derive + apply + regen (no push)
make engine-bump-daily [DRY=1]        # plan -> bump every moved engine; DRY=1 prints only
make test-engine-bump-live            # the TensorFold v1.0.5 release archive as a live end-to-end: list,
                                      # classify, checksum and RUN it (the archive path an engine bump takes)
```

The `engine-bump-rebase` workflow (daily cron `41 5 * * *`, issue #208) keeps
those open `chore/engine-bump-*` PRs current with the latest `main`: it finds
every open engine-bump PR and, when one is behind `main`, forward-merges the
latest `main` into it and force-with-lease-pushes it back — automatically, and
only when the merge applies cleanly (a conflict is left for a human). It reuses
the SAME sync logic via the shared module
`scripts/engine_bump_sync.py` (imported by `scripts/engine_bump_rebase.py`), so
there is no duplicated implementation. Run it locally with
`python3 scripts/engine_bump_rebase.py --dry` to preview without pushing.
Its collaborator guard sends `Authorization: Bearer $TOKEN`, with `TOKEN`
set to `secrets.GITHUB_TOKEN`, the same header `engine-bump` uses.

Before that commit, and only when both the old sha and the new sha are known,
the bump reads `requirements.txt`, `pyproject.toml`, and `Dockerfile` with
`git show <sha>:<path>` and keeps the names the new pin added (issue #186).
A release move compares the old tag's tree to the new tag's tree. A name
already at the old tag is not installed as new. One fixture runs that bump
through the pin and `make generate-engine-params`, and the test reads the
Dockerfile that command wrote. A pin that only removes packages prints those
names. The bump does not commit.

## Bot pipelines are isolated (issue #275)

Every bot runs on **its own pipeline**: a cron minute no other bot owns on any day, and a
`concurrency:` group of its own (`cancel-in-progress: false`) so a manual `workflow_dispatch`
queues behind its scheduled run instead of overlapping it. The current slots:

| Bot | Cron | Minute today |
|---|---|---|
| `issue-bot` | `23 6 * * *` | daily 06:23 |
| `fix-bot` | `17 * * * *` | hourly at :17 |
| `queued-alarm` | `7,37 * * * *` | twice hourly (:07, :37) |
| `engine-bump-rebase` | `41 5 * * *` | daily 05:41 |
| `registry-sync` | `19 5 * * 1` | Monday 05:19 |
| `engine-bump` | `53 6 * * 1` | Monday 06:53 |

`tests/test_bot_pipeline_isolation.py` (in `make test-unit`) expands every scheduled
workflow's cron into its `(minute, weekday)` slots and fails if any two bots share one, or if
a bot declares no concurrency group — so a future bot that lands on a used slot goes red at
`ci-unit` instead of silently racing.

## The issue-implementer (issue #248)

Nothing takes an issue and produces its first PR — until now. The
`issue-bot` workflow (`.github/workflows/issue-bot.yml`) implements ONE issue
per run, at most **3 per UTC day**, one at a time, each left as a draft-free
reviewable PR that is **never merged**. It replaces the old host watch-loop
in CI (that loop was removed in #210).

The **dispatcher** is deterministic (no LLM, stdlib only) and is the
unit-testable core — `scripts/issue_implementer.py`:

```bash
make issue-bot-dispatch REPO=asimov-agent/llgenie   # cap -> pick -> claim -> issue.md + branch
make issue-bot-open-pr REPO=<repo> ISSUE=<n> BRANCH=agent/issue-<n>-<slug>  # draft-free PR, never merges
make implement-issue      # the shared Hermes agent step: read issue.md + AGENTS.md, implement, run gates, push nothing
make issue-bot-image      # build/pull the agent image the bot runs in (same image as the fix-bot)
make hermes-smoke          # one real Hermes call through the implementer alias (die in seconds)
make issue-bot-triage     # step 1: Hermes REVIEWS the issue.md thread (body + every comment) and writes triage.md
make issue-bot-verdict ISSUE=<n>   # step 2: apply that verdict — implement | refine | close
```

**The bot decides before it implements.** It reads the issue *and its whole comment thread*
(`gh issue view <n> --json number,title,body,state,author,labels,comments` — the comments come with the
JSON, and `gh` **refuses** `--comments` together with `--json`, which is what broke every dispatch
until #268 fixed it), because the thread is where an issue is usually specified: a body
that says "add `--foo`" with a later comment "only for CPU builds" is a different issue. It then
picks ONE verdict, written to `triage.md`:

- **`implement`** — actionable as written; the branch/gates/PR path runs as before.
- **`refine`** — a real decision is still open or the acceptance criteria are missing: the bot
  posts ONE comment with an implementable restatement and labels the issue `agent:refined`. No PR
  that run; it does not rewrite someone else's issue body.
- **`close`** — already implemented, superseded, a duplicate, or not a change this repo can make:
  the bot comments the reason **with the evidence it checked** and closes the issue. A close
  whose verdict carries no evidence is **refused**, because "hard" or "vague" is a refine.

An issue labelled `agent:refined` or `agent:closed` is never picked again, so neither verdict can
loop, and neither opens a PR — so it does not consume the 3/day PR cap.
make rebase-bot-sweep     # which ONE open PR needs rebasing (BEHIND/DIRTY against main), with the reason for every pass-over
make rebase-bot PR=<n> HEAD_BRANCH=<b> HEAD_REPO=<owner>   # rebase it (agent resolves a conflict), verify, push --force-with-lease
make rebase-bot-agent     # the conflict hand-off: it asks Hermes to resolve a stopped rebase (the conflict prompt arrives on STDIN) and runs INSIDE the agent image
**Every open PR is kept on `main` by a third bot** (`rebase-bot.yml`, issue #246), because
AGENTS.md's rule is that a branch behind `main` cannot be merged — so a stale PR blocks itself.
It runs **every 6 hours** and handles **ONE PR per run**, oldest first:
- `make rebase-bot-sweep` decides *which* PR — an open, non-draft PR against `main` whose merge
  state is `BEHIND` (a clean rebase) or `DIRTY` (conflicts). It states a reason for every PR it
  passes over, skips a PR it already rebased **today** (its own marker comment is the record, so
  no label is invented and no PR is rebased twice in a day), and skips a fork it cannot push to.
- **It keeps out of the other bots' way.** It skips a PR with checks **in flight** (rebasing
  would cancel the run deciding it), and leaves a **red, merely-behind** PR to the fix-bot — a
  rebase fixes staleness, not a failing test — while still taking a **conflicted** red PR, since a
  rebase is the precondition for fixing anything on it. The implementer cannot be raced (it pushes
  a new branch and only then opens the PR, so its PRs are fresh by construction), and the refiner
  never touches a branch. If the rebase bot and the fix-bot ever do collide, the fix-bot's plain
  fast-forward push and this bot's `--force-with-lease` mean the **second one is rejected loudly**:
  nothing is clobbered in either direction.
- `make rebase-bot` does the work: rebase with `rerere` **off** (a recorded resolution from an
  earlier rebase is not trustworthy), and on a conflict hand the stopped rebase to Hermes with what
  each side means plus the hard rules (preserve both sides, never weaken a test, keep a recipe's
  TAB). Then it checks the result structurally — `make -n ci-unit` parses, `make lint`, and the
  wiring guard — and pushes with **`--force-with-lease`** to the **PR's own head remote**: a fork
  PR goes to the fork, never to `origin`. It never merges, and a resolution it cannot finish is
  reported on the PR and left for a human.
make issue-refiner-pick   # keep the backlog implementable: spare capacity -> the oldest issue that is not decided/claimed
make issue-refiner        # step 1: Hermes REVIEWS that issue (refine-in.md) and writes its verdict to refine.md
make issue-refiner-apply ISSUE=<n>  # step 2: ONE comment + the agent:refined label (never a PR)
**A companion bot reviews the backlog — the issues that have not been implemented yet.** It is a
separate workflow (`issue-refiner.yml`) that runs **hourly** and reviews **one issue per run**: open,
oldest first, not already reviewed (`agent:refined`), not claimed for implementation, and not already
linked to a pull request — i.e. an issue no PR answers yet. It opens **no PR at all**: its outcome is
ONE comment plus the `agent:refined` label, which is what stops it reviewing the same issue twice.
The only thing it refuses to do is race the implementer: while an issue is *waiting* for it
(labelled `agent:implement`/`agent:ready` with no PR yet) the run says so and yields; once that issue
has a PR it is not waiting for anyone and the next hourly run proceeds. Hermes does the *review* —
explicit acceptance criteria, scope in/out, the surfaces it would touch, and any open decision
**named as a question** rather than decided. It never rewrites an issue body and never merges.

- **Cap**: at 3 PRs already opened today (counted from GitHub with
  `gh search prs --author <bot> --created ">=today 00:00Z"`), the run logs
  `cap reached: N/3 today, next issue tomorrow`, exits 0 and changes nothing.
  Never a batch.
- **Pick**: exactly ONE issue — labelled `agent:implement` first (oldest label
  first), else the oldest open `agent:ready`. When you want a specific issue
  implemented, add the `agent:implement` label to it (or run the workflow
  dispatch with its number).
- **Claim**: a marker comment plus the branch slug, so a second concurrent run
  cannot grab the same issue.
- **The agent step** (`make implement-issue`): Hermes reads `issue.md` +
  `AGENTS.md` at the repo root and implements — Makefile-driven verification,
  no weakened or mocked tests, nothing dead (a script/test must be named by a
  make target), the issue → branch → OpenSpec → code → PR lifecycle, never
  pushes, never merges, never touches `main`. Every token (the model key, the
  owner PAT, the Nerve/JEV provider key) comes from a CI secret at run time and
  is never baked — the container's supervision is wired by #238, below.
- **Follow-ups**: once the PR is open, issue #246 keeps it rebased (one PR per
  day) and #222 repairs it when a check goes red — the implementer does not
  grow its own loop.

### The JEV decision layer in the container (issue #238)

The agent image carries the host's **Nerve plugin**, so the bots run with the same JEV decision
layer the host runs. That layer is what makes an autonomous run *cheaper and more accurate*: it
answers the cheap decisions — which step next, is this edit the right one, does this satisfy the
check, is the turn even worth starting — so the expensive model calls are spent only where they
are needed. The intended trade is **more JEV calls, fewer LLM calls**: fewer tokens, better
accuracy, and a faster run, with the context curation keeping the prompt to the part of the repo
that matters.

It is **not** a gate on the bots and not a stand-in for the review a PR gets. The bots are
autonomous: nothing in this path may stop a run.

```bash
make agent-jev-preflight   # report whether the layer is available for this run (never blocks)
make agent-image           # the image: Hermes CLI + the pinned nerve plugin + its settings + the profile
make agent-image-ref       # the GHCR ref of THIS commit's Dockerfile + install scripts (their hash)
make issue-bot-image       # the same image, for the issue-bot (alias of agent-image)
```

- **Build** (`containers/agent/Dockerfile` → `scripts/install_nerve_ci.sh`): the plugin is
  installed at an immutable commit (`hermes plugins install keeltrace/hermes-nerve --ref
  <40-char sha> --yes-deps --enable`, the v0.3.1 release commit). The wiring follows the plugin's
  own `docs/SETUP.md` and mirrors the host:
  - the documented **nervous-system block** under `plugins.entries.nerve.settings` (a value
    written one level up is never read): `nervous_enabled`, `nervous_turn_admission`,
    `nervous_mode: correct_next`, `nervous_challenge_confidence: 0.86`,
    `nervous_call_threshold: 0.58`;
  - the provider: `jev_provider: typesafe`, `typesafe_model: jev-latest`;
  - `context_engine_mode`/`context_curation_mode: apply` (`apply` is where prompt tokens are won;
    the schema default is `shadow`, which only measures) and `work_supervision_mode: advisory`
    (advisory steers without blocking, which is what an autonomous bot needs; `enforce` is a
    build arg);
  - `gate_mode: off` is deliberate: SETUP.md calls the old synchronous pre-tool gate
    compatibility behavior, not the recommended decision architecture — the nervous system above
    is;
  - the **profile sidecar** `${HERMES_HOME}/nerve/profile.json` = the host's profile `lean`
    (reflex, nervous, work_supervision, token_trajectory, receipts), written through the plugin's
    *own* `save_profile` so it is validated and atomic. A named profile is what decides which
    modules register at all, so without it the settings above would tune modules nobody enabled.
  - the dead pre-0.3.1 block `plugins.entries.hermes-nerve` is removed if a base image has it:
    Hermes never reads it, and nerve warns about it at startup.
  The build **fails** when the plugin did not land, when the ref is not an immutable SHA, when the
  profile is not one the plugin knows, or when a provider key is present in the *build*
  environment — a key in a build layer is a leak.
- **Run** (`scripts/agent_jev_preflight.sh`, reached through `make agent-jev-preflight`, and run by
  `make implement-issue` / `make fix-loop-image` before any agent work): it reports whether the
  plugin is in this `HERMES_HOME`, whether the key is available, whether the plugin is *enabled*,
  and whether the provider answers a real decision call (the plugin's own
  `scripts/live_api_smoke.py`, no stand-in). The key travels as `-e TYPESAFE_API_KEY` from the
  `TYPESAFE_API_KEY` repo secret (`issue-bot.yml`, `fix-bot.yml`) and is written into the image's
  `HERMES_HOME/.env` (mode 600), because Hermes resolves credentials per home rather than from the
  environment; the value is never printed. **When the layer is unavailable the run continues**,
  loudly: a missing key, a plugin that is not installed, a provider that does not answer — each is
  reported with what to do about it, and the bot does its work with more LLM calls and more
  mistakes for the reviewer to catch than a JEV-assisted run would make. In a workflow the run is
  **annotated** either way (`::notice` when the layer is ready, `::warning` when it is not, plus a
  line in the job summary), so "is JEV on?" is answerable from the run page instead of a log grep. `NERVE_REQUIRE=1` turns
  the report into a failure instead, and **both bot workflows arm it** (`make agent-jev-preflight
  NERVE_REQUIRE=1`): a bot run does not start with the JEV engine off — the layer is a precondition
  for an autonomous run, and an ordinary manual or local invocation keeps the report-and-continue
  behaviour.

### Manual setup (only if you don't want `make install`)

```bash
# 1. venv
cd tools && make venv-install      # create ~/llama-gguf-tools/.venv + install deps
# 2. run with the venv python
~/llama-gguf-tools/.venv/bin/python scripts/llgenie_serve.py --list
```

`requirements.in` is the single source of truth; `requirements.txt` is generated with
`pip-compile` inside the `tools/` Dockerfile container (`make generate-requirements`).

## No secret value reaches a log (#283)

Every key this repo uses travels the same way: a CI secret, `docker run -e VAR` (the **name**, never
`VAR=value`), and a guard that echoes only the variable's name when it is missing. `make
check-secret-output` (in the `ci-unit` job) keeps that true for **all** of them — `NOUS_API_KEY` /
`NOUS_PORTAL_API_TOKEN`, `GH_TOKEN` / `BUMP_TOKEN` / `GITHUB_TOKEN`, `HF_TOKEN`, `TYPESAFE_API_KEY`,
`OPENROUTER_API_KEY`, `OPENCODE_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`:

| rule | what it fails on |
|---|---|
| `secrets-in-run-block` | `${{ secrets.X }}` interpolated **inside** a `run:` block — it becomes part of the script text and of its output; pass it through `env:` |
| `prints-secret-value` | a printing command that expands a secret's value, e.g. an echo of a token variable. Printing the variable's *name*, and redirecting a value into a `chmod 600` file, are not violations |
| `xtrace-with-secrets` | `set -x` in a file that also reads a secret: xtrace prints every expansion |
| `value-in-argv` | `-e VAR=$VAR` / `--build-arg VAR=$VAR`: the value lands in the process list, not only in the environment |
| `env-dump` | a bare `env` / `printenv` whose output reaches the log |
| `key-shaped-literal` | something that looks like a live credential, committed (a deliberate test value carries `secret-output: test value` in its file) |

GitHub masks a registered secret in its own logs, and that is **not** enough: masking is a filter over
the log stream, so a transformed value (base64, a URL, a slice) sails past it, and nothing is masked in
a log a job uploads itself. `make secret-output-report` shows which files name a secret and whether any
of them prints it.

## The code-review bot (issue #269)

A bot that reads the **tree and the pipelines** and files issues for what is actually wrong. It is
**analysis, never implementation** (AGENTS.md, #231): it never edits a file, opens a PR, merges, or
comments on anyone's PR — its entire output is one issue per finding, and every issue carries the
evidence the finding came from, so a reviewer can check the claim without re-deriving it.

```bash
make code-review-scan REPO=asimov-agent/llgenie            # the checks: tree + pipelines -> findings (writes nothing)
make code-review-scan REPO=asimov-agent/llgenie STATIC=1   # skip the two checks that read the GitHub API
make code-review-file REPO=asimov-agent/llgenie            # file ONE issue per NEW finding, capped (CAP=, default 3)
make code-review-file REPO=asimov-agent/llgenie DRY=1      # preview what it would file
```

`.github/workflows/code-review-bot.yml` runs it weekly (Monday 07:23 UTC, its own slot) and on
`workflow_dispatch` for the owner/collaborators, guard first, then scan, then file.

The checks, and the two limits they are held to:

| check | what it catches |
|---|---|
| `workflow-inline-scripts` | a workflow `run:` that invokes a repo script directly instead of a make target (a step whose whole job is gh/git orchestration is exempt, as the rule says) |
| `secrets-not-defined` | a workflow reads `secrets.X` and X is not one of the repo's secrets — GitHub substitutes an **empty string**, so the job does not fail at startup, it fails later wherever that value is used |
| `workflow-never-ran` | a workflow with its own events that has never run — never verified, only reviewed. `workflow_call`-only files are exempt: GitHub counts a reusable workflow's runs under its **caller** (`ci.yml` calls `pipeline.yml` three times and reports 892 runs while `pipeline.yml` reports 0) |
| `cron-collisions` | two workflows scheduled at the same minute+hour on overlapping days (only fixed slots are compared — an hourly cron fires many times a day by design) |
| `reusable-orphan` | a `workflow_call` pipeline that nothing calls, so nothing can run it |

**Idempotent by contract**: a filed issue carries `<!-- code-review:<key> -->`, the filer skips any
key it has already filed, and a cap (3 per run) bounds a bad run — a weekly run on an unchanged tree
files nothing and stays quiet. The two API-backed checks need a token with admin to read the secret
list; without one they warn loudly and skip rather than filing a claim they cannot support.

## Dispatching a bot by hand (issue #276)
Every workflow a human can start by hand states **what work the run will do** — in its name, in its
dispatch form, and in the header block at the top of the file (`Trigger surface` / `Flow` / `Never`).
A bot you cannot dispatch without reading its YAML is a bot only its author can operate.
`make check-dispatch-forms` enforces it (in the `ci-unit` job): every dispatchable workflow must
- have a `name:` that states the work, not the file name — `issue-bot — implements ONE issue per run
  as a reviewable PR (never merges)`, so the Actions list reads as a list of jobs;
- give every `workflow_dispatch` input a `description:` (written as the instruction a user needs) and
  a `default:` or `required: true` — a bare `workflow_dispatch:` is allowed only with an explicit
  `# dispatch: no inputs — <reason>` line, so "it takes no input" is a decision, not an oversight;
- carry the header block, where `Flow` names the make target behind each stage and `Never` states the
  invariants (never merges, never pushes to `main`, never edits code).
The table below is generated from the workflows by `make dispatch-forms-report` and verified against
them by `make check-dispatch-forms`, so the documentation you read before dispatching cannot drift
from the pipeline that will run.
<!-- dispatch-forms:begin -->
| workflow | what the run does | dispatch inputs |
|---|---|---|
| `code-review-bot.yml` | reviews the tree and the pipelines and files one issue per finding (never edits code) | `dry` (optional, default `false`) — Preview the issues it would file (owner only) |
| `engine-bump-rebase.yml` | rebases every open engine-bump PR onto the latest main | `dry` (optional, default `false`) — print the PRs it would rebase and push nothing (no branch is touched) |
| `engine-bump.yml` | bumps pinned engines to their newest upstream release and opens the PR | `engine` (optional) — Only bump this engine (id); empty = all |
| `fix-bot.yml` | repairs a failing PR branch until its checks pass (never merges) | `pr_number` (optional) — PR number whose branch should be repaired<br>`branch` (optional) — PR head branch (used when pr_number is empty)<br>`check` (optional, default `make ci-unit`) — the deterministic check to drive the loop<br>`rounds` (optional, default `3`) — repair attempts (default 3) |
| `issue-bot.yml` | implements ONE issue per run as a reviewable PR (never merges) | `issue_number` (required) — Issue to implement (owner only) |
| `issue-refiner.yml` | reviews ONE not-yet-implemented issue, never opens a PR | none — the bot decides by itself which ONE issue to review (scripts/issue_refiner.py); |
| `publish-agent-image.yml` | builds + pushes the Hermes agent image when its hash is not on GHCR yet | `force` (optional, default `false`) — Rebuild + push even if the hash tag is already on GHCR |
| `queued-alarm.yml` | reports CI jobs queued far too long, once per affected run | `minutes` (optional, default `30`) — report jobs queued longer than this many minutes |
| `rebase-bot.yml` | keeps every open PR current with main, ONE PR per run (never merges) | none — the bot decides by itself which ONE PR to take (scripts/rebase_bot_sweep.py); |
| `registry-sync.yml` | syncs the vendored registry and regenerates the derived tables, then opens the PR | none — the sync has no modes: it always fetches the upstream registry, regenerates |
<!-- dispatch-forms:end -->

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
   `ARCH=`. The tag hashes the frozen variant (`llgenie/llama-cpp-prism:e8fd209c-<hash>-cuda-sm89`),
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
file exists in the image and answers the version/help flag that engine documents
(`binary_flags` in its skill: `--version` for llama.cpp, ollama, vllm/cpu and freetoken;
`--help` for sglang, strata, tensorfold, litert, mlx, exllamav3 and tensorrt-llm).
A Python import is not that check (issue #204). Those flags, and the file each image
must contain, are generated into `containers/engines/binaries.json` with the params
(`make generate-engine-params`, checked by `make check-engine-params`) and are NOT part
of the image-tag hash, so documenting them moves no published tag. A backend whose CLI
initialises its device at startup (`binary_probe: device`: vllm cuda/rocm, mlx cuda,
tensorrt-llm cuda, exllamav3 rocm) still has to CONTAIN the file; there the version comes
from `entrypoint.sh detect` (CI #106).
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

- Every Hub call (API, resolve, the `hf` CLI, and engine containers) sends `HF_TOKEN` from the environment, or from `~/.zshrc` / `~/.bashrc` when the environment is empty. CI sets that environment from the `HF_TOKEN` Actions secret (`secrets: inherit` into `pipeline.yml` and `published.yml`). The token is never stored in the repo. API GETs prefer IPv4 and retry a timed-out read with a new request; a transport failure is not remembered as an empty file tree (issue #161). A Hub 429 waits out the rate-limit window through `scripts/hf_auth.py` (`rate_limit_wait`: the `RateLimit` header's `t`, else 5 minutes, capped at 10) and is retried twice; a later success resets that count (issue #163). The size lookup, the ranged chunk download and the preflight probe open the Hub through `hub_open` in that same module, so a download waits out the same window instead of calling `urlopen` itself.
- Sets `HF_HUB_ENABLE_HF_TRANSFER=1 HF_HUB_DISABLE_XET=1` for speed.
- Auto-retries (up to 20 attempts), resuming the partial file on dropped connections.
- Appends a `.progress.log` next to the destination for live monitoring.

**Example:**

```bash
python3 scripts/hf_download.py Qwen/Qwen3.5-24B-GGUF qwen3.5-24b-q5_k_m.gguf ~/models/Qwen/24GB qwen-q5
```

## 3. Launch a model (`scripts/llgenie_serve.py`)

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
  the retry finishes (issue #180). It is retried twice; any response that is not
  a 429 resets that count. A **permanent** error
  (401/403/404) is never retried — it fails fast so a genuinely gated/dead repo is
  still reported loudly (the skip+refill and "no repos" paths above). Without this
  retry, a single 429 on one repo tree would silently drop that repo and turn a
  valid match into a false "no model fits".

Without `--family` the command behaves byte-identically to before (all existing
top-tier tests pass unmodified).

---

## Verification, loop & CI (containerized — same everywhere)

Every verification stage runs **inside the test container** so behaviour is
byte-identical on your local host (docker; on macOS through Colima) and on GitHub
Actions CI. Stages are driven **only through `make`** — the container is never
started directly.

```bash
make loop              # == make loop-harness: run ALL stages in order, GREEN gate
make test-image        # the test image (python+pytest+deps + hf + docker CLI; no inference server): pulls the
                       # published ghcr.io/asimov-agent/llgenie/test:<hash of its Dockerfile + lockfiles>,
                       # builds it here only when that hash is not published yet (an edited Dockerfile/lockfile)
make openspec-image    # the OpenSpec CLI image, the same way (hash of openspec/Dockerfile)
make ci-image-refs     # print both GHCR refs for the current files
make ci-<job>          # one CI pipeline job (ci-lint, ci-unit,
                       # ci-agents-read, ci-openspec, ci-cpu-health, ci-top-tier, ci-install): what CI runs
                       # ci-install chains, in this order: test-env -> ci-install-run (make install)
                       # -> ci-install-dry (the installed launcher, bare --dry) -> ci-install-dry-args
                       # (the INSTALLED launcher's argument surface over the mocked arch x vram x ram
                       # grid, issue #236) -> ci-install-uninstall
make lint              # linefeed/editorconfig lint (fail-closed)
make test-unit         # hermetic unit tests (all files, incl. openspec-tasks-check)
make test-agents-read  # AGENTS.md threat-pattern guard + its tests, in a make-built Python 3.12
                       # venv (~/.cache/llgenie/agents-read-venv: hermes-agent==0.19.0 + pytest;
                       # needs python3.12)
make test-install      # install tests (run in-container; host-artifact asserts — no skips via test-install-ci)
make test-install-ci   # REAL install tests, NO SKIPS: make install + model + assert in ONE container
make test-uninstalled  # after make uninstall: no launcher/shim/llgenie-engine-* left, no engine container
make test-install-host # verify the REAL host install: ~/bin/llgenie + symlinks + ~/models (runs on host)
make engine-launchers  # pull this host's published engine images (default llama.cpp + Prism; ENGINES=all|id,id;
                       # BUILD=1 builds unpublished ones) and write ~/bin/llgenie-engine-<id> + the
                       # llama-server / prism-server shims
make test-install-trend # after make install: ~/bin/llgenie with NO model in a pty -> recommended list from
                       # data/models.json -> pick 1/1 -> REAL GGUF download -> the engine container answers
                       # "hi" (issue #105)
make test-published-engine ENGINE=<id> ARCH=<arch>  # issue #102: pull ENGINE's :ARCH image AS PUBLISHED
                       # (no build, digest == the :ARCH tag), then the binary reports its version and the
                       # container serves the tiny model and answers "hi" on /v1/chat/completions
make ci-engines BACKEND=metal  # the engine stage (issue #120): cpu|cuda|rocm|vulkan -> container engines, metal -> every native engine
make test-native-engines       # Apple Silicon: make install path for EACH native-Metal engine, tiny model on Metal + "hi"
make test-native-engine        # Apple Silicon: REAL TensorFold install / update / reuse through the llgenie pick
make test-native-engine-serve  # + llgenie --select 1 --engine tensorfold downloads Qwen3.8-27B, serves on Metal (context 65536), "hi"
make test-native-engine-light  # lightest TensorFold model (Qwen3.5-9B MLX 4-bit) via the start script: Metal "hi", or the budget refusal on a 7 GB runner
make test-interactive-tensorfold                          # plain interactive llgenie: pick Qwen3.8-27B, then TensorFold -> installs, serves on Metal, "hi"
make test-interactive-tensorfold TEST_LAUNCHER=~/bin/llgenie  # the same through the launcher `make install` wrote
make test-interactive-tensorfold-ci                       # macOS CI runner variant: same picks (--dry, 48 GB emulated) + real install
# The native targets above are Metal-only: on Linux (any backend) they print that the host
# has no native engine and exit 0; Linux engines are tested in their images (make test-engine).
make test-health       # Linux: 0.5B answers "hi" through the llama.cpp image. macOS: refuses --arch cpu, no image
make test-health-host  # after make install: the same through ~/bin/llama-server (on the host, no container)
make test-top-tier     # REAL acceptance (no mocks): live HF trending + fit gate + real download
make test-top-tier-serve  # Linux: lightweight model through the llama.cpp image, "hi". macOS: no engine image
make test-top-tier-ci        # REAL top-tier acceptance inside the test container (CI/CPU; hf + gguf are bundled)
make test-top-tier-serve-ci  # Linux: serve the lightweight model through the llama.cpp image. macOS: no engine image
make test-top-tier-cli-ci # REAL CLI dry-run in the CI container: llgenie --download-top-tier --dry --count 2
make test-variant-image      # CUDA toolkit + python variant-build image, built locally (the matrix job is retired)
make download-test-model  # fetch Qwen2.5-0.5B into ~/models/Qwen/8GB (via `hf` CLI)
make lint-fix          # append a missing trailing newline to tracked text files (containerized)
make check-registry-keys     # fail when the vendored registry dropped a key, model or measurement vs the committed copy
make check-strata-models     # fail when data/strata_models.json differs from Strata's setup.py at the pinned commit
make queued-alarm      # report CI jobs stuck in `queued` too long (a runner that never picks them up, issue #254)
make openspec-validate NAME=<change>   # validate an OpenSpec change
make openspec-new NAME=<change>        # create a change dir (the OpenSpec CLI, containerized)
make openspec-status                   # list the changes and their task state
make openspec-shell                    # interactive shell with the openspec CLI in a container
make engine-detect ENGINE=<id>         # is ENGINE installed? runs that skill's detect
make engine-smoke ENGINE=<id>          # HOST entry: install the engine via its skill, serve a tiny model, assert llm-local answers
make generate-build-engine-params      # alias of generate-engine-params
make run-engine-<engine>-<arch> MODEL=…  # run one engine x arch image (e.g. run-engine-vllm-cuda PORT=11434)
make fix-bot-sweep | fix-loop | fix-loop-image | fix-bot-report  # the PR fix-bot (issues #222, #238): sweep, loop, loop-in-the-agent-image, report
make agent-image | agent-image-pull | agent-image-ref | publish-agent-image  # the Hermes agent image: pull, CI pull, ref, publish
make check-docs        # fail when a user-facing make target is not documented here, or a work record names no issue (issue #257)
make docs-report       # show every user-facing target: documented, missing, or a recorded exception
make test-clean        # prune stopped orphaned test containers (always)
```

The `make loop` harness runs these stages in order (each in its own `--rm`
container), then **always** prunes orphaned containers:

```
image → download → lint → unit → install → health → top-tier → top-tier-serve → test → openspec → clean
```

- The **`health` stage** on Linux is a real end-to-end check: it downloads the
  lightweight `Qwen2.5-0.5B` model and asserts `/health` + a chat "hi" reply
  from the **llama.cpp engine image**, started from the test container through the host docker socket (the test image holds no inference server).
  On macOS the same `make test-health` does not start an image: `--arch cpu` is refused and the native Metal serve stays `make ci-engines BACKEND=metal`.
- **Python 3.11 on both OSes:** on Linux the test stages run in `llgenie/test` (`python:3.11-slim`); on macOS the SAME make targets run natively with the 3.11 gguf venv (`~/llama-gguf-tools/.venv`), never in a container. `make test-env` prepares it (Linux: pulls the test image; macOS: `make -C tools venv-dev-install`, then `brew install uv` when `uv` is not already on PATH). LiteRT, MLX and TensorFold install as `uv` tools; a missing `uv` fails `make install` loudly.
- **`RUNTIME`** is `docker`, on Linux and on macOS (Colima with `--runtime docker`).
  `make install` reports a docker that does not answer as such, not as an unpublished image.
  `RUNTIME=<path to a docker CLI>` overrides it.
- **A slow test is shown, not hidden:** `pytest.ini` sets `faulthandler_timeout = 300`, so a
  test running over 5 minutes prints every thread's stack into the log and keeps running.
- **Required for merging into `main`** (branch protection): every Linux job and every
  macOS job. A failure on either OS fails the run. That is `linux / *`, the four
  `linux-published / install-published-*` installs and `macos / *`. No macOS job is
  `continue-on-error`. macOS has no published-image stage and no native-engine job: it
  never runs an inference server in a container, so there are no images to test there,
  and GitHub's macOS runners have no Metal GPU to serve on.
- **One CI run per change, not per push:** `ci.yml` triggers on `pull_request` against
  `main` and on `push` to `main` (a merge, which additionally builds and publishes the
  engine images) — never on a bare feature-branch push. So a branch is vetted by its PR's
  run, and the merge commit's run is the publish path. A fork PR is vetted by the upstream
  run and its checks report on the PR (issue #155).
- **Only collaborators, the `github-actions[bot]`, and the owner may trigger the
  workflows:** `ci.yml`, `registry-sync.yml`, `engine-bump.yml` and `engine-bump-rebase.yml` gate every run behind an actor guard that
  fails unless the triggering actor is the repo owner, the `github-actions[bot]`, or a
  collaborator (checked via the GitHub API collaborators endpoint). This is defense-in-depth
  on top of the fact that a push to a fork already runs the workflow in the fork (its own
  GHCR), never upstream — so a non-collaborator can never drive the upstream's GHCR publish
  jobs (`ci-images`, `engine-base`, `engine-matrix` in ci.yml; `sync` in registry-sync.yml; `plan`/`bump` in engine-bump.yml).
- **CI images are pulled, never rebuilt per job (issue #117):** the first job, `ci-images`,
  tags `llgenie/test` and `llgenie/openspec` with a hash of the files they are built from
  (`scripts/ci_images.py`) and runs `make publish-ci-images`: a hash already on GHCR is one
  manifest lookup, a new one is built once for linux/amd64 + linux/arm64 (registry layer
  cache) and pushed to `ghcr.io/<owner>/llgenie/{test,openspec}:<hash>`. Every other job
  (Linux, macOS, `engine-image`, `test-published-*`, `install-published-*`) runs
  `make test-image-pull` / `make openspec-image-pull`, which fail instead of building when the
  tag is missing.
- **The same CI pipeline on Linux and macOS:** `.github/workflows/ci.yml` calls ONE file,
  `pipeline.yml`, twice: `linux` (ubuntu-latest) and `macos` (macos-15-intel). Linux sets
  up Docker; macOS runs the same `make ci-<job>` targets in the Python 3.11 gguf venv
  and never starts Colima. No macOS job calls the Docker action. Engine images are the
  Linux published stage. OpenSpec on macOS installs the pinned CLI.
  The early `install` job runs `make ci-install` on both OSes. That target only prepares
  the environment, then runs `make install`, `$HOME/bin/llgenie --dry` and `make uninstall`
  as separate make targets. macOS runs them in the Python 3.11 venv and never starts a
  container. The `macos` job is `macos-15-intel` (`x86_64`): `make install` there installs
  no Metal engine and pulls no image, because LiteRT, MLX and TensorFold publish arm64
  wheels only — and because nothing was written, the `test-built-engine` and `uninstall`
  steps that follow are a no-op that exits 0 (nothing to version-test, nothing to remove).
  Apple Silicon still installs every native Metal engine. Linux runs
  `make install`, the dry run and `make uninstall` inside the test container, so the dry
  run sees the launcher `make install` just wrote.
  Native-Metal engines are not tested in CI (no Metal on the runners); run
  `make ci-engines BACKEND=metal` on an Apple-Silicon host. Every job is one `make ci-<job>` target (lint, unit,
  install, agents-read, openspec, cpu-health, top-tier), the same job on both
  OSes, same asserts, no combined jobs (issue #120). Docker is set up only on Linux
  (`.github/actions/docker`); macOS never runs it. `tests/test_ci_images.py` locks that both OSes call the one file.
- **Native Metal engines, on an Apple-Silicon host (issue #120):** `make ci-engines BACKEND=metal`
  (no CI job: GitHub's macOS runners have no Metal GPU):
  every servable engine with a Metal backend (`model_engine_pick.metal_engines()`: litert,
  llama.cpp, llama.cpp-prism, mlx, ollama, tensorfold) is installed natively by its skill —
  llama.cpp and the Prism fork are BUILT from source with `-DGGML_METAL=ON` — prints its
  version and serves a tiny model on Metal answering "hi".
- **One pipeline, per-OS engine set (issue #120):** the macOS pipeline is literally the
  same pipeline as Linux — the same `make ci-<job>` targets, in the same order, with the
  same asserts. The only divergence is the **engine matrix**: Linux builds/tests the
  container engine images it supports; macOS installs/tests the native-Metal engines it
  supports (issue #114 — Metal cannot run in a container). At the end each OS runs
  `make install` **for each engine it supports, in that engine's own environment** and
  proves it works (Linux in CI: the container engine answers "hi"; macOS on an
  Apple-Silicon host: the native engine serves on Metal and answers "hi"). No engine is built or tested on the wrong platform,
  and no supported engine is skipped.
- **Every make command runs its corresponding Python script (issue #120):** each top-level
  `make` target is a thin shell entrypoint that runs a Python script in `scripts/` (install,
  engine skills, launch/tune/health, CI). The same script runs on both OSes — inside the
  docker test image on Linux, inside the 3.11 venv (and natively for Metal) on macOS. There
  is no hidden `_install` internal command API.
- **bash 5 is the recipe shell on both OSes (issue #120):** the Makefile resolves `SHELL`
  to brew's bash on macOS (bash 5) and `/bin/bash` on Linux (also bash 5). `make bash-check`
  — a prerequisite of `install`, every `ci-*` target, `loop` and `chained` — installs bash
  via `brew install bash` on macOS when it is missing and fails closed if the recipe shell
  is not bash 5, so no stage ever runs under macOS's system bash 3.2. The Makefile exports
  that shell as `LLGENIE_BASH`, and `engine_runner` / `engine_smoke` run their `bash -c`
  under it — a bare `bash` on the macOS CI runner is `/bin/bash` 3.2, invoked as a login
  shell, which drops the 3.11 venv from PATH. The readiness fixture is
  `scripts/loopback_server.py`, not `python3 -m http.server`: on the macOS 15 runner
  that module calls `socket.getfqdn()` between bind and listen, and the lookup stalls
  ~35s, so a 30s probe reports the server dead while it is still alive. The check
  lives in `scripts/check_bash.py` (single source of truth).
- **No CI job or step is skipped:** each OS has its own pipeline file, and nothing carries a
  `runner.os` / matrix / event condition. OS- and matrix-specific work is decided in make:
  `make ci-free-disk` frees disk on a Linux runner and only reports on macOS, and
  `make test-engine-stage TEST=serve|detect` is the one post-build test step of every engine
  image (serve: `make test-engine`, detect: `make test-engine-image`). The engine images are
  built once (Linux containers), then `published.yml` (`make ci-engines BACKEND=<b>` ->
  `make test-install-published` per backend) installs them on Linux in every push run (macOS
  never runs an engine container, so it has no published-image stage).
- **One engine stage, the only per-OS row (issue #120):** `make ci-engines BACKEND=<b>`
  (`scripts/ci_engines.py`). `BACKEND=cpu|cuda|rocm|vulkan` runs `make test-install-published`
  (container engines, CI `linux-published`); `BACKEND=metal` (Apple-Silicon host only, no CI job) runs
  `make test-native-engines` — `make install`'s path for EACH native-Metal engine (litert, mlx,
  ollama, tensorfold): skill install at the pin, start-script version, a tiny model served on
  Metal answering "hi" — plus `test-native-engine`, `test-interactive-tensorfold-ci` and
  `test-native-engine-light`. Every stage runs; any failure fails it.
- **Python 3.11 everywhere (issue #120):** the test image and the lockfile image are
  `python:3.11-slim`; the gguf venv is created with Python 3.11 (`scripts/check_python.py`,
  which `brew install`s python@3.11 on macOS when missing, and on Linux auto-provisions
  it via `uv python install 3.11` when `uv` is on PATH — or finds a uv-managed 3.11 even
  when it is not on PATH; a non-3.11 venv is recreated).
  `make test-install-ci` ends with `make test-uninstalled` (no installed file, no engine
  container left). make install picks this host's images by itself: on a Mac the cpu
  images (linux/amd64, run through Rosetta), and llgenie offers only trending models whose
  engine has an image for this host.
- **CI** (`.github/workflows/ci.yml`) triggers on a `pull_request` against `main` and on a
  `push` to `main`; it is the hub, and calls the reusable `pipeline.yml` once per OS
  (`linux`, `macos-15-intel`), which runs each stage as its own **parallel** job: `lint`,
  `unit`, `install`, `openspec`, `cpu-health`, ... Every job is a `make ci-<job>` command, so
  CI == your local loop.

### PR fix-bot & the agent (Hermes) image (issues #222, #238)

The Hermes agent image is what repairs a red PR in CI, so it gets its own publish path
instead of riding the test/openspec images:

```
make agent-image        # pull the hash-tagged Hermes image (its Dockerfile + install script), else build it here
make agent-image-pull   # CI: pull the published agent image as llgenie/agent:latest; fails when missing, never builds
make agent-image-ref    # print the GHCR ref for the current Dockerfile + install script
make publish-agent-image  # build + push ONLY the agent image (linux/amd64) when its hash tag is not there yet
```

`publish-agent-image.yml` is `workflow_dispatch`-only, re-checks that the actor is the
owner/a collaborator with write before any secret is read, and pushes with the owner PAT
(the default `GITHUB_TOKEN` is denied "Create organization package" for a brand-new
package). It is `linux/amd64` only: building Hermes under arm64 emulation times out. The
image is hash-tagged, so re-running it is a no-op unless its inputs changed.

The fix-bot (`fix-bot.yml`: hourly `schedule` + `workflow_dispatch`) repairs the branch,
re-checks and stops — it **never merges**; a human reviews the result:

```
make fix-bot-sweep      # which red PR deserves the bot, then dispatch it (DRY=1 previews; needs gh)
make fix-loop           # run the loop locally against the failing check (scripts/fix_loop.sh; needs an agent on PATH)
make fix-loop-image     # the same loop inside the agent image (AGENT_IMAGE= overrides the ref, LOG=path tees)
make fix-bot-report     # render the loop's failure report (REPORT=<path>) — the comment the workflow posts
```

The loop runs the failing check, hands the failure to Hermes and re-checks, up to
`FIX_ROUNDS` (default 3). The loop itself never commits or pushes; the workflow pushes
the repaired tree as ONE commit with the owner PAT (so CI re-runs) only when the loop
ends green.

### Documentation is part of the change (issue #257)

A change is not done until the docs the user reads describe it. Two rules, both
enforced in `ci-unit` by `make check-docs` (`scripts/check_docs.py`):

1. **Every user-facing make target is documented here, in the same change.** A target
   that `make help` prints (its recipe carries a `##`) must be named in this README —
   whole-token, so `docs-report` does not document `docs`, and a pattern target
   (`run-engine-%`) is documented by its stem. A target that deliberately stays out of
   the README is recorded in `tests/fixtures/docs-exceptions.json` with a reason, a
   date and the issue; `make check-docs` fails when that record goes STALE (the README
   documents it after all) so the file cannot rot.
2. **Every `agent-wiki/` work record references the issue or PR it implements** (`#<n>`).
   A work record that names no issue is unfalsifiable, and `make check-docs` fails it.

The same applies to a workflow, feature, stage or behaviour change: mirror it in the
README's matching section and update the `agent-wiki/` entry in the same commit, before
the PR is ready. `make check-docs` catches a target the README never learned about;
the reviewer reads the rest. `make docs-report` shows the whole picture (documented,
missing, recorded exceptions, and each work record's references).

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
│   └── engine-bump-rebase.yml  # daily: rebase open engine-bump PRs onto the latest main (issue #208)
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
  unknown name fails loudly instead of silently falling back (issue #247). The resolved
  value is the one used by the context budget, the GPU-layer count, `-ctk`/`-ctv` and the
  plan printed by `--dry`.

- `make agent-image-push-check` proves the **credential can actually push** the agent image
  before a ten-minute build: it asks GHCR for a push-scoped token and initiates the cheapest real
  write there is (an empty blob upload), then prints the registry's own refusal if it is denied.
  It exists because the publish once burned a full build and died with `permission_denied:
  create_package` — a PAT cannot create a package in an org its owner is only a collaborator of,
  while the workflow's own `GITHUB_TOKEN` can (it is what created `llgenie/test`,
  `llgenie/openspec` and `llgenie/strata`). The workflow therefore logs in with the default token
  and calls this first.

## How the bots stay out of each other's way

Four bots (`issue-bot`, `issue-refiner`, `fix-bot`, `rebase-bot`) write to the same issues and PR
branches, so each one announces what it is doing **on the subject itself** and reads the thread
before it picks anything:

    <!-- bot-claim: refiner 2026-10-14T22:10:03Z refine ttl=180m run=123456 -->
    <!-- bot-done:  refiner 2026-10-14T22:41:55Z refined -->

- A bot claims the issue/PR first — one comment, **before** its first mutation, so a sibling can see
  it in time.
- **A recent comment that has not been concluded by a `done` comment means someone is on the
  subject**, so the run *skips it and takes the next one in the list* — it never stands down for the
  whole run. That is why the schedules are not the race protection.
- **The marker carries the terms the reader applies** (issue #292): `ttl=<minutes>m` is the writer's
  own window (the same number the human sentence names it with), and `run=<id>` is the run holding
  it. A reader honours the announced `ttl` — its own default is only the fallback for a marker
  written before that field existed — so a 30-minute rebase no longer blocks a 4-hour repair.
- **A run that is over releases its claim immediately** (issue #291): the reader asks GitHub about
  `run=<id>` and, when that run is finished or cancelled, takes the subject and prints why. An
  unreadable run state is *unknown*, which never releases a claim.
- A `done` marker releases it, and **it says which kind of done**: `refined`, `closed`, `merged`,
  `cancelled` and `repaired` release the subject, while **`pr-open` keeps occupying it** — implemented
  but not yet approved must not be implemented a second time.
- `make test-unit` runs the rule (`tests/test_bot_claims.py`, `tests/test_issue_refiner.py`,
  `tests/test_issue_implementer.py`, `tests/test_fix_bot_sweep.py`, `tests/test_rebase_bot_sweep.py`);
  `scripts/bot_claims.py` is shared **byte-identically** by all four bots, so whoever merges first
  makes the other three no-ops.
