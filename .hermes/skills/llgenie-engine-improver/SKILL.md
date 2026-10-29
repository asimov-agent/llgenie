---
name: llgenie-engine-improver
description: Use when a trending engine needs syncing, a skill/params/image rebuilt, or an engine's serving params tuned on this host's GPU — the LLGenie engine loop.
version: 1.0.0
author: Asimov Agent
license: CC-BY-4.0
metadata:
  hermes:
    tags: [llgenie, inference-engines, docker, serving-params, trending-local-llms, cuda]
---

# LLGenie engine improver — the operating loop

## When to Use

Load this for ANY work on LLGenie engines: a new trending engine that needs a
skill/params/image, a rebuild or build failure, a serving-speed tuning question,
a "model missing from the trend list" report, or a change to the picker/selection
logic. It is the default frame for this profile's sessions.

Profile copy (what loads on the host): `~/.hermes/profiles/llgenie-engine-improver/skills/software-development/llgenie-engine-improver/SKILL.md`.
Change BOTH in the same change set: this copy is what a reviewer reads and what CI validates as a
HOST skill; that copy is what actually runs.

## Mission (the priority order, not a suggestion)

**The main repo is `llgenie`.** `trending-local-llms` is the upstream STORE — syncing it is the
means, never the goal. In this order:

1. **Sync the engines that are new or updated and have Linux support** into `llgenie`
   (`sync-registry` → gap report → skill → `generate-engine-params`), so their Dockerfiles are
   regenerated and CI can build the images.
2. **Run those engines locally, on this host's real hardware**, against the local LLM the picker
   would select — pull the published image, serve, measure.
3. **Fine-tune the running parameters per inference server** for that model and THIS card
   (context vs KV headroom, offload, kv-quant, slots, flash-attn), and land the value in the
   engine skill so the generated params carry it.
4. **Maintain and improve the llgenie script and its selection** — `llgenie_serve.py`,
   `model_engine_pick.py` and the trending list must only offer a model × inference server pair
   the hardware can actually run, and the pair must be the fastest one that hardware can run.

Everything else in this skill is the mechanics of those four. When a session drifts into registry
bookkeeping or CI plumbing with no engine ever being run, it has left the mission.

This is the standing job, not a one-off task: keep the LLGenie engine chain
green and make each engine actually run fast on THIS host. Work happens mainly
in the `llgenie` repo, which CONSUMES the `trending-local-llms` registry.

```
trending-local-llms  data/models.json          (which engines + models trend)
        |  make sync-registry  -> llgenie/data/models.json
        v
skills/engines/<id>/SKILL.md                    (one per engine; the only place
        |  make generate-engine-params           build/serve facts may live)
        v
containers/engines/params/<id>.json + dockerfiles/<id>-<arch> + binaries.json
        |  check-engine-params / -coverage / -source ; engine-build.yml matrix
        v
ghcr.io/asimov-agent/llgenie/<id>:<hash>-<arch>   (published image per engine x arch)
        |  make engine-launchers
        v
~/bin/llgenie-engine-<id>  ->  scripts/llgenie_serve.py   (the picker the user runs)
```

Every link is generated from the one before. A break high in the chain shows up
far down as "the model vanished from the trend list" — always walk DOWN from the
registry, never patch the symptom at the bottom.

## Inputs

- The two checkouts: `llgenie` (the work) and `trending-local-llms` (the upstream store), with
  `llgenie-wt` / `trending-local-llms-wt` for parallel branches.
- `make engine-skill-gap` — per-engine status: shipped, known-unsupported, NEW-AND-UNRESOLVED, plus
  the models no shipped engine can offer.
- `skills/engines/<id>/SKILL.md` — the engine's pin, per-backend build recipe, binary, launch line.
- The host: `nvidia-smi` (card + driver), `docker` + the NVIDIA CDI entry, `nproc`, RAM. Every tuned
  answer is a function of these, never of a remembered flag.
- The published images in GHCR for this arch, and the launcher scripts the host has for them.

## Output

- A reviewable PR per concern (never a merge): the engine skill edit, the regenerated
  `containers/engines/params/*` + Dockerfiles + `binaries.json`, the derived tables, and the tests
  that fail on the parent and pass on the fix.
- For a tuning pass: the exact serving parameters, each traceable to a flag the PINNED image itself
  prints in `--help`, plus the measured tokens/s of the run that justified them.
- A report that names the broken link, the command that proves the fix, the measured number, and
  what still waits on CI or the user's merge.

## Step 0 — orient (every session, before touching anything)

```bash
cd /home/asimov/repository/git/llgenie && git status --short && git log -1 --oneline
cd /home/asimov/repository/git/trending-local-llms && git log -1 --oneline
make engine-skill-gap          # shipped / known-unsupported / NEW-AND-UNRESOLVED
make engine-skill-gap-md       # same, markdown, for a PR/issue body
```

State the current HEADs and the gap before changing anything; the answer to
"what is new" is that report, never a guess. Worktrees `llgenie-wt` and
`trending-local-llms-wt` exist for parallel branches.

## Step 0b — cut from a fresh upstream main, and bookend the work (#873 rule 15)

Before creating a worktree or branch: `git fetch upstream main` — the canonical remote is
`asimov-agent/llgenie`, and a fork named `origin` is **not** upstream — then branch from
`origin/main` **at the sha you fetched in that moment**. Never from a branch you already had, and
never from a sha quoted in a chat message: it is stale by the time you read it.

An engine bump cut from a stale `main` builds engines that no longer exist — the third way the same
bump fails, and it looks identical to the other two (#807: the awaited tags were absent; #893: the
30-minute wait outlived the queue).

**Bookend the work in the thread, never in a DM:**

- **start comment** — issue/PR id, branch, the `main` sha you cut from, and what "done" means;
- **finish comment** — head sha, what changed, the run id or command that proves it, and anything
  left open.

A start with no finish is an abandoned claim; a finish with no start has no baseline to compare
against. For an engine wait, the same thread carries `producer job + run id + sha`.

## Step 1 — sync new/updated engines that have Linux support

- `make sync-registry` vendors the store into `data/models.json` + the contract
  and README. Report what changed with `make registry-change-report`, and file the
  change as an issue with `make sync-change-issue` if it is a real delta.
- The sync job is deliberately LENIENT (`--allow-new-engines`): a new engine lands
  even though it cannot ship yet, because a store that cannot land also cannot
  spawn the issue that resolves it. The STRICT gate (`make check-engine-skill-gap`)
  runs in the normal CI unit stage and is what reds until the engine is resolved.
- `make spawn-engine-skill-issues` opens one tracking issue per new unskilled
  engine. Every such issue must name its FIRST command (the scaffold target with
  its `ENGINE=`/`ID=`/`BACKENDS=` knobs, then validate, then
  `generate-engine-params`) — otherwise the implementer re-derives the key set.
- **The Linux-support filter is explicit, never inferred.** An engine whose only
  backend is Metal (mlx, omlx, Apple-only apps) cannot build or run here; it gets
  a DATED, REASONED entry in `data/unsupported-engines.json` (read the upstream
  README/releases — not the registry's one-line auto-registration note) and no
  skill. An engine that later ships a skill, or that upstream stops listing, is a
  STALE entry and the gate fails until it is deleted. "No decision" is not a
  decision.
- Ownership: the SYNC bot carries a new engine; the BUMP bot only re-pins engines
  that already have a skill (it derives from `skills/engines/<id>/SKILL.md`, so it
  can never create one). Never send new-engine work to the bump bot.

## Step 2 — skill -> params -> Dockerfile

```bash
make engine-skill-scaffold ENGINE='<registry name>' ID=<kebab> BACKENDS='CUDA / CPU' DRY=1
make check-engine-skill-gap
make generate-engine-params ENGINE=<id>
make check-engine-params check-engine-coverage check-engine-source
```

- Scaffold writes the facts the registry states and leaves everything
  unprovable EMPTY (`ref`, `pinned`, `install.<backend>`, `binary`, `detect`,
  `launch`, `health`, `alias_mode`, `license`). A guessed pin or apt package is
  worse than an empty one because it BUILDS; the validator turns empties into an
  ordered to-do list (`missing <key>` / `needs <key>`).
- A failed backend parse must FAIL LOUDLY with the offending string plus the
  explicit override — never default to CUDA (that is how a ROCm-only engine
  lands on an image nobody can run).
- `append accepted build flags` only through the documented-params path
  (`engine-params-review` -> `-apply`), which requires the flag AND its quote to
  be present in the engine's own file at the pinned sha. No flag from memory.
- **The image matrix is derived from the params** — a new engine needs NO
  workflow edit. Do not add per-engine CI jobs by hand.
- A `servable: true` skill with no container backend block emits NO params entry
  and NO Dockerfile, so it silently never enters the build matrix. After adding
  a skill, assert a Dockerfile exists for every declared backend.
- Commit generated artifacts. A green local `generate` that was never committed
  is the most common red.

## Step 3 — never build an engine image locally; pull the published one

**The engine BUILD belongs to CI.** `.github/workflows/engine-build.yml` builds every
engine x arch cell from the committed params and publishes
`ghcr.io/asimov-agent/llgenie/<id>:<hash>-<arch>`. This host does NOT compile an engine:
no `make build-engine` / `build-engine-base` / `build-engines`, no `docker build`, no
source checkout, no toolchain bake. Local GPU time and disk are for RUNNING.

- After a params change, wait for that CI cell and PULL:
  `docker pull ghcr.io/asimov-agent/llgenie/<id>:<hash>-<arch>`, or
  `make engine-launchers ENGINES=<id>` which resolves the exact tag the launcher uses.
- A missing tag means the CI cell has not published yet — check the workflow run. Never
  fall back to building it here: a locally built image is unverifiable against the pinned
  sha and diverges from what every user pulls, so a "pass" proves nothing about the
  artifact that ships.
- Proof of an engine is the PUBLISHED image answering its own `detect` command with the
  pinned version — match a version shape (semver, or `pin <sha7+>`), never merely digits.
- A GPU-less CI runner cannot answer a `--version` that probes the device
  (`libcuda.so.1` ImportError). Package metadata proves the WHEELS are installed, not that
  the binary runs — a weaker verdict, counted separately.
- The image TAG is derived from the params: edit a start/`pre_launch` step and the launcher
  resolves a tag that does not exist locally or in GHCR yet. Check `docker images` and the
  `engine-image-<id>-<arch>` job before saying "test it now".

## Step 3b — verify a published engine end to end on the host

Pulling is only half; the engine must answer. Run this whole sequence after a param
or pin change, using the PUBLISHED image and never a local build:

```bash
make engine-launchers ENGINES=<id>     # resolves + pulls the exact tag the launcher uses
make test-built-engine                 # every ~/bin/llgenie-engine-* prints its version
~/bin/llgenie-engine-<id> --version    # one engine, in isolation
```

Then serve a real model through the picker and prove the OpenAI path:

1. Start the launcher in a TRACKED background process (the terminal tool refuses
   `nohup`/`&`/`setsid` in a foreground command — that check fires on the wrapper, not
   on your intent), redirecting to a log:
   `~/bin/llgenie-engine-<id> <local-model> <port> > /tmp/llgenie-serve.log 2>&1`.
2. Poll `curl -s http://127.0.0.1:<port>/v1/models` until the alias `llm-local` appears;
   check `docker ps` shows the container `Up (healthy)`.
3. Send one real `/v1/chat/completions` request and read the timings block. The
   `system_fingerprint` (`b<build>-<sha7>`) is the pin proof; `predicted_per_second` is
   the tuning number — compare it to the registry's claimed t/s, do not invent one.
4. `docker rm -f llgenie-<id>-<port>` and confirm the container is gone before reporting.

A `--version` that passes while the start line dies on an argument the server rejects is a
false green; only step 3 proves the launch line.

**Which backends this host can actually verify.** `cpu` and `cuda` run here (NVIDIA card + CDI
`nvidia.com/gpu=all`) — serve a model and read real timings from them. `rocm`, `vulkan` and
`metal` have no device on this host: the only honest check is the PUBLISHED image answering
`docker run --rm <image> version` (plus `<binary> --help` for the flags), which proves the
binary and its argument surface, NOT the compute path. Say exactly that in the report; never
let a `--version` on a foreign-backend image read as "verified on this card".

**A DISABLED image cell is a cell that does not exist**: `engine_image.DISABLED` removes it from
`--engines`, from the launcher's choice and from the CI matrix, so the engine silently resolves to
its `cpu` variant on a GPU host. That is how `llama.cpp-prism` (the only reader of Ternary Bonsai
2's PQ2_0/PTQ1_0 types) had no GPU image at all. Enabling a cell is a code change plus a params
change, then a dispatch:
`gh workflow run engine-build.yml --ref <branch-in-the-upstream-repo> -f engine=<id> -f arch=<v> -f push=true`
— a branch pushed to `origin` (asimov-agent) publishes; a fork-head branch does not.
Verified after the fix: the picker routes a PQ2_0 file to `llama.cpp-prism`
(`gguf_tensor_types` reads the header, `PRISM_GGML_TYPES = {142,143}`), and the published prism cpu
image serves it (`llm-local`, fp `b10772-e8fd209c9`) at 10.4 prompt / 2.47 gen t/s — CPU speed on a
27B ternary, which is why the cuda cell matters.

**A model the engine cannot read looks like a hang, not an error.** Serving
`prism-ml/Ternary-Bonsai-2-27B` PQ2_0 (a ternary GGUF, tensor type 142) through stock
`llama.cpp` exits 1 in ~2 s having printed only the launch line: llama-server's real
message (`tensor 'output.weight' has invalid ggml type 142`) went into the container-local
log. That model needs the **Prism** build. Before blaming the launcher, dump that log
(`docker exec … cat /tmp/engine-runner-serve.log`) — and note `llama.cpp-prism` has **no
cuda image** (disabled: "fat CUDA build runs > 50 min on hosted runners") and its cpu tag
was unpublished here, so on this card such a model is not runnable at all until CI
publishes or the disable is revisited. Never solve that by building locally.

## Step 3c — a wait on an image is a TWO-LANE dependency (#873 rule 14)

Before any wait for an artifact another job produces, **name the producer on the PR and to the lane
that owns it**:

```
waiting on engine-image-<engine>-<arch>, produced by job <job-name> in run <run-id>
```

- A claim belongs in the thread a stranger can find — the issue or PR — never only in a DM or in
  memory. Re-read that thread before the first edit: an existing claim, a live branch or a note from
  the lane that touched the files last outranks your plan.
- When the producer sits behind a long queue, message that lane with the id, the sha and what you
  need, **then post the conclusion back in the issue**; a decision that exists only in a DM does not
  exist for the next reader.
- The precedent is #807: the awaited tags did not exist because the producer cells were still
  `pending`, and the 30-minute wait (#893) expired on the queue rather than on a bad tag. Read the
  producer's job state **before** blaming the artifact, and say which of the two it is — a missing
  artifact is a fact to report with its log, never a reason to park a PR.
- Rebase, rewrite or force-push on a branch another lane is working is a conversation first, a
  command second.

## Step 4 — tune the serving params per engine on the real GPU (the core value)

This is the part the job exists for. A built image is not a tuned engine.

1. **Discover the accepted flags from the image itself**, at the pinned sha:
   `docker run --rm --gpus all <image> <binary> --help` (and the fork's own
   `--help`/README section — forks rename and add flags). Build the candidate
   list from that output, not from memory.
2. **Fill the card, don't just avoid OOM.** Target weights + KV cache + a batching
   reserve inside 16 GiB, then push context as far as that headroom allows. A
   quant sized to the whole budget leaves nothing for KV and is the classic
   wrong answer.
3. **Per-engine, the levers differ** — treat these as the axis, verify names:
   - llama.cpp / Prism / forks: `--n-gpu-layers` (all), `--flash-attn`,
     `--ctx-size`, `--cache-type-k/-v` (kv quant), `--batch-size`/`--ubatch-size`,
     `--parallel`, `--jinja`, `--no-mmap`, `--tensor-split`, `--threads`.
   - vLLM: `--gpu-memory-utilization`, `--max-model-len`, `--kv-cache-dtype`,
     `--enable-chunked-prefill`, `--max-num-seqs`, `--enforce-eager` (only when
     CUDA graphs break).
   - SGLang: `--mem-fraction-static`, `--context-length`, `--chunked-prefill-size`.
   - Ollama: `OLLAMA_FLASH_ATTENTION`, `OLLAMA_KV_CACHE_TYPE`,
     `OLLAMA_NUM_PARALLEL`, and `num_ctx` in the model parameters, not a flag.
   - Own-checkpoint engines (Strata, TensorFold, TensorRT-LLM): the plan function
     decides the quant/shards; the runtime args are the engine's own.
4. **A tuning claim needs a number from a real run.** Use the engine's own
   benchmark (`llama-bench`) or the server's reported timings on a fixed prompt
   set; compare old vs new params on the SAME image, same model, same quant.
   Never write a t/s figure that did not come from output. If a run cannot be
   made, say which step blocked and what the next alternative is.

   The published images build only `llama-server` (no `llama-bench`), so measure by
   POSTing to `/v1/chat/completions` with `temperature: 0` and a fixed `max_tokens`,
   then read `timings.prompt_per_second` / `timings.predicted_per_second`. The engine's
   load log is NOT on `docker logs` — the runner writes it to
   `/tmp/engine-runner-serve.log` inside the container, so read it with
   `docker exec <name> cat /tmp/engine-runner-serve.log` while the server runs.

   Measured baseline (4090 Laptop 16 GiB, llama.cpp cuda image, 27B UD-IQ3_S at 11.2 GB,
   same prompt): llama.cpp's auto-fit spends 15 052 MiB on 4 slots x 53 504 ctx for
   170.8 prompt / 37.40 gen t/s; `-c 32768 -np 1 -fa on -ctk q8_0 -ctv q8_0` gives
   196.9 / 37.74 at 12 420 MiB; 64k costs 1.25 GB and 5% prompt speed for no gain.
   Flash-attn + q8 KV + one slot is the safe one-user default; a hard-coded `-c` is not
   (it is wrong for every other model) — derive the context from the KV headroom the
   weights leave, the way the quant planner already derives the quant.
5. **Land the tuned value in the SKILL, then regenerate.** Params live in the
   skill; editing a generated `params/*.json` is reverted by
   `check-engine-params`. Then let the CI cell rebuild/publish the new tag and
   PULL it (step 3) before running — never build it here.
6. The image tag changes with the start params — so a tuning change is a
   build+CI cycle, not a hot edit.

## Step 5 — improve the picker and the trend selection

`scripts/llgenie_serve.py` (the `~/bin/llgenie` launcher), with
`scripts/model_engine_pick.py`, `scripts/trend_list_matrix.py` and
`data/trending-quant-catalog.json` are the selection logic: how much VRAM/RAM/arch
-> which model -> which inference server -> which exact HF quant file.

- The offered-engine contract is per (model, engine): **offered <=> the engine
  has a runnable image for this arch AND some quant fits the weight budget**. A
  model can appear because ONE engine fits; report a skipped row WITH its reason,
  never as silent absence.
- Ranking keeps only engines with an image variant, so an unskilled engine drops
  its models out of the list silently — that is a registry problem (step 1), not
  a picker bug.
- Drive the grid as a reproducible command: `--vram V --ram R --arch A` override
  the detected host so CI can assert the whole permutation set. Test against the
  REAL vendored registry, stub only the Hub tree, and keep the file-existence
  check on the LIVE Hub (ranged 1-byte GET, 200/206).
- Regenerate the committed derived tables after a registry change:
  `make render-trend-list-matrix check-trend-list-matrix`,
  `make sync-quant-catalog check-quant-catalog`,
  `make render-engine-skill-gap check-engine-skill-gap`.
- The download must reuse the plan already shown to the user (same engine, same
  RAM budget) — recomputing defaults fetches a quant the engine refuses.

## Proving a fix, pitfalls, versioning

The branch/proof recipe (stash → branch from origin/main → fail on parent → pass on fix),
the traps that cost real time in this tree, and how the `.hermes/skills` gate treats a HOST
skill: `references/proving-and-pitfalls.md`.

## Rules

- **Never merge, and never arm auto-merge — everything is the owner's decision (owner directive 2026-10-29).** No squash, no merge by hand, no `gh pr merge --auto`, no push to `main`. This lane stops at a reviewable PR; a "done" rewrite is a ready-for-review PR, never a merged `main`. This lane holds merge AND arm for the owner — it does not arm the way tester-style lanes do; a finished, unarmed PR waits for the owner, which is this lane's explicit contract.
- **Rebase only when actually conflicting (owner rule #1015).** Do not rebase a PR onto every `main` move; keep its merged baseline and rebase only on a real conflict. `git fetch upstream main` before any work stays, with an explicit refspec — never the ambiguous `origin/main` shadow. On a co-owned branch (#1000/#1004 style) the branch owner's conflict resolution wins; never force-push over it.
- **Report done+PR to the planner and check for a `bot-claim:` before shared-branch work (#1010).** Report every done+PR to `@llgenie-planner`; version behaviour under `agents/llgenie-engine-improver/` via issue+PR confirmed with `make sync-agent-profile PROFILE=llgenie-engine-improver CHECK=1`; re-read the thread for a `bot-claim:` and state the one you take before the first edit.
- **Never build an inference-server engine image locally.** CI builds and
  publishes every engine x arch cell (`.github/workflows/engine-build.yml`);
  this host pulls and RUNS. No `make build-engine*`, no `docker build`, no
  source compile. A locally built image proves nothing about the artifact users
  pull, and a missing tag means CI has not published yet — not that you should
  build it.
- No fabricated bench numbers, no invented flags, no "should work". Report the
  real exit code and the real output.
- Undo experiment side effects (containers, clusters, worktrees).
- **Do not stop while work remains.** Finish the loop end to end; when one link is
  blocked (CI cell not published, image missing for this arch), continue down the
  chain with what IS runnable and report the blocked link plus its next command.
  "Go" means land the change, open the reviewable PR, then run the host
  verification — not just describe the plan.
- **A defect you found is a fix to ship, not a finding to report.** "No skipping" is the
  standing expectation: reproduce it, patch the rule AND its test, open the reviewable PR, get
  the image published (same-repo branch + `gh workflow run … push=true`), pull it and prove the
  host path. Handing back a list of blockers with no PR is a failed pass; the only acceptable
  blocker is one no code change can move (an unpublished cell still building, a fork head that
  cannot publish).
- Deep per-engine detail — hardware parameter mapping, pin bumps, source
  conversions, matrix tests — is in `local-inference-engine-builds`; load it
  before doing build-flag or pin work rather than re-deriving it here.

## Report shape

Name the link that was broken, the command that proves the fix, the tuned params
with the measured number, and what still needs CI or the user's merge.
