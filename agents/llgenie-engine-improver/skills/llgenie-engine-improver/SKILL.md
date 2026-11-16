---
name: llgenie-engine-improver
description: "Run the LLGenie engine loop: sync, build, tune, verify."
version: 1.0.0
platforms: [linux]
author: llgenie-engine-improver
license: MIT
metadata:
  hermes:
    tags: [llgenie, inference-engines, docker, serving-params, trending-local-llms, cuda]
---

# LLGenie engine improver — the operating loop

<!-- host-bot-tools:begin -->

## Tools

This lane's chat session is pinned to these Hermes toolsets and no others: `clarify`, `code_execution`, `file`, `memory`, `session_search`, `skills`, `terminal`, `todo`.

Skills that stay enabled: `github`, `llgenie-engine-improver`.
Every other installed skill is listed in `skills.disabled`.
The pin is `tests/fixtures/host-bot-capabilities.json` in asimov-agent/llgenie (issue #1038).
<!-- host-bot-tools:end -->

## Role artifact (2026-11-01)

An engine or serving change is this lane's pull request, not `llgenie-issse-implementer`'s. When the PR is up, arm auto-merge (`gh pr merge <n> --squash --auto`) and read `autoMergeRequest` back. Do not approve: the author cannot approve its own PR. Then `message_agent` to `llgenie-planner` with the PR number, the head sha, and the arm time. The arm is a readback, not an exit code: re-read `.autoMergeRequest` after arming; `null`
(e.g. `mergeable_state=blocked` on a red check) means NOT armed — report `auto=none (blocked: <check>)`.
**The arm does not survive a base move**: when `main` advances into a conflict GitHub disarms
(`autoMergeRequest: null`, `mergeable_state: dirty`) and the CI runs already at the head were measured
against the old base, so rebase → re-push → re-arm → re-read, and re-run the checks rather than quoting
the old greens. Details in `references/ci-run-watching.md`.

**A `fix(engines)` PR branches on the CANONICAL repo, never the fork (owner directive 2026-11-03).**
`engine-build-pr-trigger` refuses a foreign (fork) head — "a foreign-head bump cannot trigger a
push=true dispatch" — so a fork-headed engine PR can never run the producer that builds and publishes
its cells. Open the branch on `asimov-agent/llgenie` in-repo (push to `origin`, not the `andyholst`
fork), and read the PR's `head.repo.full_name` back = `asimov-agent/llgenie` before relying on any
trigger. #1568 died that way (fork head refused); #1696 is the same fix re-opened in-repo.

**A new `scripts/<tool>.py` in an engine PR must carry `# proc-allow:` on every `subprocess.*` line.**
`check-proc-gate` (issue #797) confines `subprocess.run`/`check_output`/`Popen` in `scripts/` to
`scripts/proc.py` or a same-line `# proc-allow: <reason>` — so a fresh launcher script (e.g.
`hip_offload_parallel.py`) reds `make ci-unit` (`[proc-gate] N bare subprocess call site(s)`) the
moment it is added. Tag each raw toolchain/device-compile call with its reason from the start; verify
with `make check-proc-gate` (expect `0 bare`) before pushing. Proof gate to trust: the census line
`N allowed, 0 bare`. A "0 stale"/"OK" from the gate after `check-engine-params` does not mean the run
passed — the earlier `check-proc-gate` may have already aborted `ci-unit`; read the abort line
(`Makefile:<line>: check-<gate> Error 1`) from the CI job log, not the last gate that printed.

Supporting depth lives in `references/`. To read engine-build CI verification runs correctly (pending
vs. genuinely building, dispatch run vs. the PR's CI run, dispatch-by-branch-not-SHA, and when a run
may supply a measured acceptance number), see `references/ci-run-watching.md`.

## A build change opens its follower at PR time (issue #1085)

An engine build change — a change to HOW cells are built (source-build, pin, Dockerfile, toolchain,
`entrypoint.sh`, `engine_runner.py`) — cannot be proven by the author reporting `available -> no
rebuild`, which is a cache hit on an image CI already published and carries no build timing. So every
such change opens a **follower issue, delegated to this lane, AT PR time** (not after merge), scoped to
execution rather than review:

1. dispatch `engine-build` COLD at the PR head — `gh workflow run 395994204 --ref <branch> --field
   engine=<id> --field arch= --field force=true --field push=true` — and quote the run id;
2. serve at least one cell to READY from the just-published image and record the stage `detect` output;
3. record per-cell build wall-clock (job step timings) and image size (published manifest) beside the
   run id in the change note;
4. post the re-measured acceptance criteria on the implementing PR/issue with quoted commands.

The lane's "CI is the sole builder" rule does not block this: the pipeline result carries the timing
(the reconcile at line 864 — a wall-clock / image size comes from CI, never a local build). First
instance: #1085 → #1075 (ollama ×4).

## When to Use

Load this for ANY work on LLGenie engines: a new trending engine that needs a
skill/params/image, a rebuild or build failure, a serving-speed tuning question,
a "model missing from the trend list" report, or a change to the picker/selection
logic. It is the default frame for this profile's sessions.

Versioned copy: `$HOME/repository/git/llgenie/.hermes/skills/llgenie-engine-improver/SKILL.md`
(this profile's skill is the installed copy; the repo copy is what a reviewer reads and what CI
validates as a HOST skill — change BOTH in the same change set).

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

## Step 0 — orient (every session, before touching anything)

```bash
cd "$HOME/repository/git/llgenie" && git status --short && git log -1 --oneline
cd "$HOME/repository/git/trending-local-llms" && git log -1 --oneline
make engine-skill-gap          # shipped / known-unsupported / NEW-AND-UNRESOLVED
make engine-skill-gap-md       # same, markdown, for a PR/issue body
```

State the current HEADs and the gap before changing anything; the answer to
"what is new" is that report, never a guess. Worktrees `llgenie-wt` and
`trending-local-llms-wt` exist for parallel branches.

**Cut from a fresh upstream main, and bookend the work (#873 rule 15).** Before creating a
worktree or branch: `git fetch upstream main` — the canonical remote is `asimov-agent/llgenie`,
and a fork named `origin` is **not** upstream — then branch from `origin/main` **at the sha you
fetched in that moment**. Never from a branch you already had, and never from a sha quoted in a
chat message: it is stale by the time you read it, and an engine bump cut from a stale main
builds engines that no longer exist — the third way the same bump fails, looking identical to
the other two (#807: awaited tags absent; #893: the wait outlived the queue).

Write the sha into your **first comment** on the issue/PR (id, branch, main sha, what "done"
means) and a **last** one when you finish (head sha, what changed, the run id or command that
proves it, anything left open). A start without a finish is an abandoned claim; a finish without
a start has no baseline. An engine wait states it in that thread: `producer job + run id + sha`.

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
- **To verify the cpu+cuda pipeline without publishing, dispatch `engine-build` twice (ARCH=cpu then
  ARCH=cuda) with `push=false`.** Each run does build -> test-engine-stage for every cell of that arch, so it
  proves the params->matrix->cell->build->serve path without touching GHCR (the serve-leg
  `test-published-engine` and install-leg `test-engine-install` gate on `push=true`, so a pushless run never
  reaches them). Confirm the guard + matrix pass and the spawned cell rows match the params census; a `push=true`
  sweep republishes the fleet and is the owner's call — a cpu sweep you fire without that word may be cancelled
  back at you.

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
   The launcher also removes that container when the process that started it exits
   (issue #1669). A parent that is still waiting on the launcher has not exited, so
   this `docker rm` is what ends a serve you backgrounded yourself.

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

**Enabling a cell, and what each backend can prove here:** `references/engine-image-cells.md` — the
GPU-less build probe that kills a cuda cell (`libcuda.so.1`, exit 127), the publish recipe for a
same-repo branch, and why a change to `engine_runner.py`/`entrypoint.sh`/a Dockerfile moves every tag
and reds `test_ci_publish_order` for engines that change never "repinned".

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

Before any wait for an artifact another job produces, **state it on the PR and to the lane that owns
the producer**:

```
waiting on engine-image-<engine>-<arch>, produced by job <job-name> in run <run-id>
```

- A claim belongs in the thread a stranger can find — the issue or PR — never only in a DM or in
  memory. Re-read that thread before the first edit: an existing claim outranks your plan.
- When the producer sits behind a long queue, message that lane with the id, the sha and what you
  need, **then post the conclusion back in the issue**; a decision that exists only in a DM does not
  exist for the next reader.
- The precedent is #807: the awaited tags did not exist because the producer cells were still
  `pending`, and the 30-minute wait (#893) expired on the queue rather than on a bad tag. Check the
  producer's job state **before** blaming the artifact, and say which of the two it is.
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
- **A measured run admits a model only on hardware the HOST's arch can reproduce — never gate a
  container/GPU host (cuda/vulkan/rocm/cpu) on an Apple/Metal "unified memory" run.** An MLX
  "M1 Pro 16GB" row beside a "M4 Max 128GB" must not offer that model on a 16 GB cuda card, but a
  measured run on the host's OWN kind of card DOES admit even when `vram_min` is larger (the
  declared minimum is NOT a hard floor over a qualifying run; a weights-only fit admits above it
  too). The fix is ARCH, not a vram_min early-reject: thread the host arch into
  `fits`→`card_evidence`→`admitting_measurement`→`trend_list`→`recommend`, defaulting `None` = a
  bare gate call counts every card-sized run (so the #669 run-wins / weights-admit semantics hold),
  while the container-host offer passes its arch and skips Apple "unified memory" runs (M1/M4/
  "unified memory"/Metal hardware). The test `_fits_names` helper must pass the same arch as the
  `offer` it asserts against — a bare `fits` that weights-admits an Apple-only model while the cuda
  offer excludes it reds `names == fits_names`. `vram_tier` is a display bucket, never the gate.
- A model whose only engines are Apple (MLX only) has no runnable image for the host arch and is
  excluded there on that ground alone, whatever its sub-card weights fit.
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

## Working a test/CI refactor in this tree (issue-class "real-call tests out of the gate")

The full working method for this issue-class lives in `references/test-ci-refactor-method.md` — load it whenever you work a test/CI refactor in this tree (moving real-call tests out of scratch/host lanes into CI-unit, fixture re-generation, skip policy).

## Proving a fix, pitfalls, versioning

The branch/proof recipe (stash → branch from origin/main → fail on parent → pass on fix), the
authorised way to ship a branch another lane rebuilt (rebase `--onto`, re-author to an allowed
identity, `--force-with-lease` against a freshly fetched sha), and the **two-lane reshape of a shared
branch** (cherry-pick a range when rebase-resume hangs, tmp refs for cross-env object reachability,
net-tree verify before the ONE lease) live in `references/proving-and-pitfalls.md`, alongside the
traps that cost real time in this tree and how the `.hermes/skills` gate treats a HOST skill.

Adding an engine-side producer test leg to the build matrix — the `make test-engine-install` seam
(install + dry + uninstall of the just-published image per row) AND the separate post-publish SERVE leg
(`make test-published-engine`) that the seam alone would silently drop (install only version-checks the
binary; the published image's serve/"hi" must be its own leg), plus the make-seam gate discipline
(drop `##` to be internal, add to `.PHONY`, pin with a workflow-structure test) — lives in
`references/engine-install-leg.md`.

**A red `make build-engine` cell is a closed loop with five mandatory steps — the lane is OWED the
rebuild-and-republish follow-through, and a report must not stop at "classified + tracked".** When the
engine-build matrix lands a red cell, resolve it end-to-end before it counts as done, as ONE sequence:
(1) **open the failing leg's OWN log** — run id + job id + head sha — and quote its error line (a
`conclusion` is a verdict, not a cause; the read-log-before-claim rule in SOUL); (2) **classify the leg**
per `references/publish-run-adjudication.md`: a `build-engine` failure = image never built (real
publish-path defect), a verify-gate red = `push-engine` SKIPPED → tag missing (acceptance gap, not
verify-only), a `push-engine` success with a later `install-leg` red = image IS in GHCR, verify-class
only — the class determines whether a re-publish is even owed; (3) **fix that cell only** — its
params / Dockerfile / install-leg, never a sibling's cause generalized over the matrix (a multi-arch run
can carry three unrelated root causes — read each cell's own log); (4) **re-dispatch the SINGLE
engine×arch** (`gh workflow run 395994204 --ref <branch> --field engine=<id> --field arch=<backend>`,
mechanics in `references/engine-build-proof-dispatch.md`) with `push=true` only when the fix touches a
publish-path input — **never a full `engine="" arch=""` sweep** — and quote the new run id; (5)
**confirm the fresh GHCR tag before calling the cell resolved** — probe
`scripts/ghcr_publish_probe.sh <leaf> <tag>` → `PUBLISHED`, because a missing tag is
indistinguishable from never-built. A cross-invocation base no longer forces a full sweep: the
internal-stage base (#1753/#1756) means a republish of ONE cell republishes only that cell at its ref.

**Read the failing job's log before any dispatch or any green/red/reviewable claim (#1791-AC3).** This
lane's SOUL carries the read-the-failing-job-log-first discipline verbatim; the full mandatory sequence
(open the failing step's OWN log — run id + job id + head sha —, quote the error line, and attribute the
root cause to that gate before dispatching or claiming a verdict) loads from the canonical #1791
procedure reference via `references/read-the-failing-job-log-pointer.md`.

**An empty queue triggers the own-domain continuous-improvement audit, not idleness (owner 2026-11-01,
#1774).** When this lane's reactive queue is empty, run a bounded, measurable audit of its domain and
produce the next finding — the two named domains: **engine-cell pin validity** (a pinned engines/params
ref that is silently unsatisfiable — #1252/#1262-class — before a build blows up on it) and **serving
drift** (a capability the engine no longer delivers vs `data/engine-capabilities.json`, e.g. an arch
serve-capability that has lapsed). The mechanics of pin-validity and capability checks live in
`references/pin-audit.md` and `references/registry-contract-following.md`; use `make skills-validate` /
the quant-catalog / the trend matrix to confirm a cell's true state before calling it drift. File every
finding as a refined six-section issue routed through the normal queue — implementation is another
lane's pass, **never this lane's own** (this lane implements only its own skill/behaviour). A clean
audit is recorded as `re-audited at <sha>, no findings` and reported on the board. The sweep runs only
when the queue is empty; it never overrides real reactive work that has landed.

This profile's behaviour is itself a repo artifact (`agents/<profile>/SOUL.md`, manifest and gate):
`references/agent-profile-soul.md` — including why a `SOUL.md` write needs explicit user approval and
must not be routed around, the gate's rule that the tree SOUL must be a SUPERSET of the live profile's
SOUL, and how to tell a pre-existing gate red (other lanes' drift) from your own regression.

**Syncing the profile skill into the repo-copy HOST skill is a CONTENT-ADD into the gate-compliant
structure, never a verbatim overwrite, and the copy can hold the WRONG lane's rule.** The repo copy
(`.hermes/skills/<profile>/SKILL.md`) must keep `## Inputs`, `## Output` and `## Rules` — a blind
profile→repo copy drops those and reds `check_agent_skills` (the profile skill is written for the agent
without the extra headers; the repo copy is the CI-validated artifact). Before trusting the repo copy,
verify its `## Rules` carry THIS lane's contract — a stale copy can hold a different style lane's rule
(a tester-style "arm auto-merge when done" where this lane never arms), which misleads every reviewer
the moment they read it. Keep the repo copy's structure, add the missing producer/workflow facts into
the section that covers them, and re-run `make check-agent-skills` + its test to green before the PR.

**A dispatch's path label for a profile row is a claim about a filename, not a measurement** — enumerate
`~/.hermes/profiles/<profile>/skills/*/` with sizes and match the row by bytes/file-count before copying
anything; clearing the row (verbatim dir copy, `diff -rq` empty, every named reference shipped, base-diff
attribution of the failing test legs) is the recipe in `references/agent-profile-soul.md`. A dispatch's "N of M files identical" is likewise a claim — measure EACH file with `diff -q`; a reference `.md` can drift +22 lines while the `SKILL.md` drifts +8, so copy every differing file verbatim, not the one the dispatch named.

**Build a PR body with a heredoc file, not a long quoted `printf`/`--body "…"` string.** A body with
backticks, `$`, parens and nested quotes gets re-parsed by the shell wrapper and fails with
`unexpected EOF while looking for matching` — write `/tmp/body.md` with `cat > … <<'EOF' … EOF`, then
`gh pr edit/create --body-file`. Then read it back (`--json body --jq '(.body|test("<phrase>"))'`) to
confirm the line landed.

**Find the live skill's actual directory before editing or syncing it — the profile can hold it at a
different path than the tree versions.** `skill_manage` writes to whatever path the live profile already
uses, so a skill living at `skills/<category>/<name>/` keeps receiving edits there while the repo reads
`agents/<profile>/skills/<name>/`; the two never meet and the lane looks like it forgets rules it keeps
recording. Locate every copy first (`find ~/.hermes/profiles/<profile>/skills -maxdepth 3 -type d -name
<skill>`), then `diff -rq` the live copy against the repo copy: a **path-only** divergence needs a `mv`
into the canonical location (no content merge — the files are already identical), while a genuinely
different pair is unioned **by section**, never wholesale, because a line-wise copy strips blank lines
and fences and the linefeeds lint then reads shell comments as headings. Removing the duplicate path is
host state, not a repo change, and it is what stops the next write landing in the wrong copy.

## Non-negotiables

- **A check that does not run cannot pass, fail, or hold.** Before claiming a PR is `held red` or `green`, read the *run* at its current head (`gh run view <id> --json status,conclusion,attempt,headSha` and its `jobs`) — not just the check-run names, and never a local `pytest`. #1099's `faf5943a` carried four sub-minute greens (`scope`/`holds`/`guard`) while **`linux/unit` never ran**; the "held red" was a local measurement reported as though a gate shared it, and a green board row meant nothing in either direction (#1137). Three pushes in two minutes had cancelled each CI in turn — `cancel-in-progress` turns a verdict into no verdict. The same holds for a gate that CRASHES: an aborted check prints no FAIL line, so its caller sees an empty scan and reads it as clean — "found nothing" and "could not tell" produce identical output, and only the exit status plus a non-empty summary distinguishes them. Push nothing until the run at the head concludes; recovery from a cancelled run is `gh run rerun <id>` (same sha), never another push.

- **Unreachable is not nonexistent.** `git log --all` and `for-each-ref --points-at <sha>` enumerate **refs**; a head that a force-push replaced is reachable from no ref, so both return nothing while the commit still exists on the server. To decide whether a sha exists use `git cat-file -t <sha>` (a local object) or `gh api repos/<owner>/<repo>/commits/<sha>` (the server) — and to decide whether it is *the PR's* head use `gh api repos/<owner>/<repo>/pulls/<n> --jq .head.sha`, nothing else. Report "unreachable from any ref", never "does not exist", unless `cat-file` also fails.

- **A regen's reproducibility and its correctness are different problems — fix both before regenerating a golden.** A hermetic render (a recorded Hub snapshot) only means the same output every time; if the selection path is wrong, the hermetic regen bakes the wrong row just as faithfully. Measure both: does it reproduce, and does every changed field match what the product should claim. `trend_rows` and `rank_engines` disagreed: `rank_engines(cpu)` ranked a phone's plain `llama.cpp@6.0` first (same_hw=True) for a model whose ternary weights no plain build can load, while `matrix()` chose the PrismML fork. Making `trend_rows` follow the ranking made it strictly worse — establish which path is authoritative BEFORE aligning them.

- **Do not reach for `xfail` to document a known defect in this repo — use an ordinary assertion that reds on the defect's disappearance (a canary).** `tests/conftest.py` has two skip guards that disagree: `pytest_report_teststatus` marks every skipped report failed (no xfail exemption) while `pytest_runtest_logreport` explicitly exempts `wasxfail`. An xfail whose test fails is therefore RED, while an xpass is green — the same marker behaves two ways (#1121 tracks the contradiction). A canary (`assert n > 0`, `assert checked > 0`) states the defect is present and reds when it is fixed, which is the lifecycle xfail's `strict=True` was meant to give.

- **Before regenerating a golden fixture, diff it FIELD-BY-FIELD against main — not line-count, not "it renders".** If the regen changes `server` or `tps` (not just provenance like `measured_on`/`variant`), it is baking a NEW product claim, and the honest move is to hold the PR red with the reason in the body, not to regenerate. Measure it with a script that keys on `(model, field)` and counts cases. A regen that greens the suite by recording a claim the product does not make is the defect, even when every test passes.

- **`git checkout HEAD -- <file>` reverts EVERY uncommitted change in that file, not just the experiment you meant to drop.** Reverting one probe (a ternary-routing heuristic) also wiped a committed-in-spirit-but-uncommitted `measurement_backend` fix in the same file, and the fix shipped absent while the PR body described it — a test caught it only after a rebase. After reverting an experiment, **diff the file against your intended state** (or keep the fix as its own commit before probing), and never trust the PR body's description over `git show <head> --stat`.

- **A test marker sits where the behaviour is, or the scan measures a proxy.** When a live test is refactored into a helper + a hermetic twin + a `@network` wrapper, the `@pytest.mark.network` must move to the **wrapper that makes the live call** — not stay on the helper. A marker left on the helper makes the routing census attribute it to the twin, i.e. the scan counts a live call that no longer exists there. Same rule as "trace the call, not the imports": the marker must sit on the code path that actually reaches the network, or the gate measures the wrong thing.

- **A ternary/prism model routes to the PrismML fork ONLY — prism cpu fallback when the prism-cuda cell is disabled, never plain `llama.cpp` — and the ROUTING SIGNAL is the per-FILE GGUF tensor type, never a per-MODEL word.** Ternary GGUF (`GGML_TYPE_PQ2_0`=142, `PTQ1_0`=143) does not load in stock `llama.cpp` ("upstream loads only the Q2_0 file"). A registry-side heuristic ("any engine's quant/weight says ternary → strip non-prism engines") is **too broad**: `Qwen3.8-27B` carries BOTH a ternary/prism variant and non-ternary `llama.cpp` variants, so the heuristic strips its legitimate `llama.cpp` row (`KeyError: 'llama.cpp'` in `test_engine_tps_comes_from_the_hosts_hardware_first`). The only correct signal is the file's GGUF tensor type (`gguf_needs_prism` / `GGML_TYPE_PQ2_0`=142, `PTQ1_0`=143), and the registry carries no tensor/host field on a model's engine rows — so ternary routing is blocked on `registry-sync` recording the tensor type per file. Do not force a per-model heuristic; hold the matrix golden — but skip/xfail is FORBIDDEN here (`AGENTS.md` "no skips allowed"), so the interim is a RED pending PR, never an `xfail` marker, and never a regen that bakes the ternary-on-plain-llama.cpp row into the golden.

- **The sync leg must WORK and its output must be LEGIT — verify both.** New trending data must actually arrive from `andyholst/trending-local-llms` through the `registry-sync` pipeline (it is `disabled_manually` today — re-enabling is owner-only, so report the blocker rather than assume it ran). And a sync that runs is not enough: the synced store must be **verified against its source** — the model + inference-server rows trace to the upstream repo, each engine's supported arch types are recorded (not hand-edited), ternary/prism packings carry a signal the pick can route on (tensor type or an explicit marker), and `make skills-validate` / the quant-catalog / the trend matrix all agree with the synced data. A sync that silently drops tensor types or mangles arch support produces a "legit-looking" store that mis-routes models — that is the failure this leg exists to catch. Never treat "the pipeline is green" as "the data is correct".

- **Per trending inference server, verify the arch → Dockerfile → Linux image → params chain.** The inference-server list from `andyholst/trending-local-llms` states each server's supported arch types (cuda, cpu, vulkan, rocm). For EVERY supported arch there must be: (1) a generated Dockerfile at `containers/engines/dockerfiles/<engine>/Dockerfile.<variant>` (plus the `containers/engines/base/Dockerfile.<backend>` toolchain it FROMs); (2) a params entry in `containers/engines/params/<engine>.json` under `variants`; and (3) an actually-built **Linux** image (`linux/amd64`) on GHCR whose tag hashes the pinned ref + params + Dockerfile + entrypoint + runner. A supported arch with no Dockerfile, or a Dockerfile never built into a Linux image, is a gap — say so. Audit at `ac12cae9`: all 13 engines have a Dockerfile for every supported variant (0 missing); the build/publish + platform leg and the #1027 install-leg are what remain red.

- **A report/mapper arch-or-format claim is read from the repo's own parser, and it is a CLAIM to verify — never a fact.** Read each engine's declared capability from `engine_skills.load_skills()` (`backends`, `formats`, `os` per engine) — do NOT grep the SKILL.md front-matter: a heredoc'd regex loses its backslashes through the shell (unterminated-string SyntaxError) and a hand-rolled `grep -E '^backends:'` misses the inline-list form `backends: [cuda, rocm, …]`. The declared set is what the skill *says*, and none of the existing gates prove it is real: `test_every_supported_arch_has_a_generated_dockerfile` (#1107) only proves every DECLARED arch has a Dockerfile — never that it is an arch upstream actually supports — and the `Servable`/`Backends` table in `docs/ENGINES.md` is prose no gate enforces. Confirm arch support against the engine's upstream README/releases at the pinned sha, never the registry's one-line auto-registration note. The `formats:` field is the model-format claim: ternary GGUF (`GGML_TYPE_PQ2_0`=142, `PTQ1_0`=143) is servable by the PrismML fork ONLY — so "engine X can load model Y's file" was an unvalidated pairing until a docs-cited per-engine arch+format table backed it, and a mis-route surfaces as a serve-time hang, not a sync error.

- **That table now EXISTS and is a CI gate: `data/engine-capabilities.json` + `make check-engine-capabilities`.** It is the docs-cited mapper the sync leg lacked: one entry per shipped engine (`archs`, `formats`, `ternary`), checked against what the tree actually declares, so a faulty trending entry reds at sync-time instead of failing at build or hanging at serve. The subset checks are the contract: **E1** every skill `backends:` ⊆ mapper `archs`, **E2** skill `formats:` ⊆ mapper `formats`, **E3** every params `variants` key ⊆ mapper `archs`, **E4** a ternary type (`PQ2_0`=142/`PTQ1_0`=143) is servable only by a `ternary:true` engine (only `llama.cpp-prism`), **E5** every mapper engine has a skill and every skill has a mapper row. When the registry/engines change, add or adjust the mapper row in the SAME change — do not let the gate go red to be "fixed" later. It is wired into `ci-unit`, `.PHONY`, `docs/ENGINES.md` and `issue_bot_gates.DEFERRED` (an unclassified `ci-unit` gate reds the issue-bot gate). The `ternary` signal is `PQ2_0`/`PTQ1_0`, NOT the older `TQ1_0`/`TQ2_0` (upstream `llama.cpp` reads those); triggering E4 on `TQ*` is too broad.

- **Every session: check the engine-build pipeline AND the sync pipeline, and fix what is red.** Read the latest `engine-build` runs and separate a genuine failure from a documented gap (#103 build-time libcuda). Read `registry-sync` (the sync from `andyholst/trending-local-llms`) — it is `disabled_manually` today, so the trend list is not syncing; re-enabling is owner-only. When a genuine error appears, **research it (web) before patching** — a current upstream flag/known-issue beats a guess. Known live example: the #1027 install-leg (`make test-engine-install`) fails for EVERY cuda cell because it calls `engine_skills.py install`, which correctly exits 3 for a container-only engine ("installed in its container image, not on the host") — the leg must test the container path (pull/serve/`test-built-engine`), not host install. A cell's image can build + serve green while its install-leg is red; check both.

- **THE CORE LOOP (this lane's whole job): sync → arch → build → offer, and verify each leg.** (1) Sync the trending local-LLM list and trending local inference-server list **from `andyholst/trending-local-llms`** — not hand-edited. (2) Know each engine's **supported arch types** (cuda/rocm/vulkan/cpu/metal) from the sync. (3) For every supported `(engine, arch)` cell, verify it **builds and publishes a Docker image** (`engine-build`); a cell that is "supported" but does not build is a **gap**, and a disabled cell must carry its #103-class reason + a documented fallback. (4) Only then does the picker offer a model+server pair — and only when the run's `measured_on` matches this host's arch and a card it can reproduce. The picker must never offer a pair that (a) the engine cannot load, (b) was never built, or (c) was measured on other/unknown hardware. Detail: issue #1092.
- **`measurement_backend()` defaults to CPU, never CUDA — and changing that default REQUIRES stating the explicit CUDA case.** The classifier returned `"CUDA"` for any hardware it did not recognise, so a `CMF Phone 2 Pro (on-device)` run and an `iPhone 18 Pro Max` run both bucketed CUDA and were admitted as cuda measurements (the `APPLE` regex `apple|M[1-9]|mac` misses "iPhone"). Fixes: `APPLE` gains `iphone|ipad` (→ Metal); `_CPU_HW` gains `phone|on-device|android|galaxy|pixel` (→ CPU); the default becomes **CPU**. THE TRAP: the old CUDA default was LOAD-BEARING — it caught every `_CUDA_HW` token (rtx/nvidia/geforce/tesla/dgx/…) because no branch returned CUDA for them explicitly, so flipping the default silently turns `RTX 3060`/`RTX 4090`/`H100` into **CPU** (a real regression caught only by re-running the table). So add `if any(k in hw for k in _CUDA_HW): return "CUDA"` — plus a generic `\bgpu\b` → CUDA for an unnamed "8GB GPU" (`"no gpu"`/`"cpu only"` are already CPU via `_CPU_ONLY`) — BEFORE the default. Verify against the WHOLE table (RTX/DGX/"8GB GPU"→CUDA, RX/Strix Halo→ROCm, Pi/"cpu only"/phone/unknown→CPU, M5/iPhone→Metal): a phone-only check passes while RTX→CPU ships. Any "measured_on" verdict must be reproducible from the hardware string; a phone is never a cuda result.
- **A build wall-clock / image-size measurement comes from CI, never a local build.** Dispatch `engine-build` for the cell(s); read wall-clock from the job step timing (`gh api repos/…/actions/runs/<id>/jobs --jq '.jobs[].steps[]|select(.name|test("build"))|{name,started_at,completed_at}'`, quoting the run id beside the numbers — a wall-clock without a run id is a claim about time), and image size per cell from the pushed manifest (`docker manifest inspect` / registry digest). A cached `available -> no rebuild` is **not** a measurement: leave the acceptance criterion NOT MET rather than substitute the author's cached number. An honest gap is actionable; a cached number looks like evidence and cannot be told apart from one. Probe the per-cell size from the MOVING per-arch tag `ghcr.io/asimov-agent/llgenie/<id>:<variant>` (the pinned tag is `llgenie/<id>:<pin8>-<digest8>-<variant>`, so the digest is unknown before the run; the `:<variant>` tag is republished every push and its manifest layer sum IS the size) — token flow: `read GHCR_AUTH="${GHCR_USER}:${GHCR_TOKEN}"; T=$(curl -s -u "$GHCR_AUTH" "https://ghcr.io/token?service=ghcr.io&scope=repository:asimov-agent/llgenie/<id>:pull" | jq -r .token)` then `curl -s -H "Authorization: Bearer $T" -H 'Accept: application/vnd.docker.distribution.manifest.v2+json' https://ghcr.io/v2/asimov-agent/llgenie/<id>/manifests/<variant> | jq '[.layers[].size]|add'`. **A published-cell CENSUS uses the PINNED tag, never the moving `:<variant>` tag — and a "missing" cell must be classified against `engine_image.DISABLED` before it is called a gap.** The moving `:<variant>` tag is only republished by a push SWEEP, so an engine nobody has repushed recently answers 404 on it while its pinned image is live; using it as the census yields phantom gaps (measured: 13 "MISSING" that resolved to 4 DISABLED cells + 1 mid-build + the rest simply un-repushed — every declared variant actually had a Dockerfile and a correct base image). The identity a launcher pulls is `ghcr.io/asimov-agent/llgenie/<id-dashed>:<pin8>-<digest8>-<variant>` — dotted ids become dashes (`llama.cpp`→`llama-cpp`) — computed by `engine_image._current_tag(params, variant)`; resolve that path + token for the manifest, and read `engine_image.DISABLED` (`(id, v) -> reason`) to separate a real gap from a disabled #103 cell. A **303** from the probe is a wrong repo path / token scope, not absence — **404** is the genuine miss. (`make -s engine-build-matrix` = every declared cell; `matrix(ci=True)` drops the DISABLED ones — the gap between the two IS the disabled set.) **A cold build dispatched with `--ref main` checks out main AT DISPATCH — if main moves mid-run, an install-leg/recipe red belongs to the CHECKED-OUT sha, not tip.** Read the run's `head_sha` and compare to current main before attributing: a `test-engine-install` red on a container-only engine is the pre-fix host-native recipe if tip has already switched it to `make engine-launchers` — an artifact, NOT a build failure, so do NOT post the AC verdict or open the PR from that run; re-dispatch on the fixed sha. A **~1 s install-leg red that FOLLOWS a green serve-leg** (build + detect + push + serve-leg all passed, only install-leg failed near-instantly) is exactly this pre-fix signature: the cell is green for build/publish/serve, and only the stale host-install recipe failed — read the step timings (`gh api .../actions/jobs/<id> --jq '.steps[]|{name,conclusion,started_at,completed_at}'`) to confirm the red is sub-second and downstream of a passing serve, not a real engine failure.

- **Pre-check a gate on the tree CI actually runs: `git merge-tree`.** Before pushing, reproduce the merge: `git fetch fork '+refs/heads/<branch>:refs/remotes/fork/b'` then `T=$(git merge-tree --write-tree origin/main refs/remotes/fork/b | head -1)`; `git archive $T | tar x -C /tmp/merge`, then run the gate there (`python3 scripts/check_import_roots.py ratchet` — **`ratchet`, never `check`**: `check` is the unfiltered report that reds on clean main, #1066). For a cross-repo PR fetch the **fork**, not `origin` — `origin` may hold a different `fix/<branch>` at another sha and give a false red; confirm `git rev-parse --short` equals the PR's `headRefOid` first. This turns "CI is the only real check" into a 30-second local test.

- **"Is this test hermetic?" — trace the CALL, not the imports.** `tests/test_trend_list_matrix.py` imports no `http`/`urlopen`, yet `tlm.trend_rows()` → `_no_fit_reason` → `gguf_weights` → `_hub_json` makes a live Hub GET per case (disk-cached `HUB_CACHE_TTL=3600s`, so a cold CI runner hits the Hub and a warm local cache hides it). "No network import" proves nothing when a helper does the network — follow `trend_rows`/`fits`/`_no_fit_reason` down to `_hub_json`/`hub_open`. A golden regenerated against live data is CURRENT, not DURABLE; say so in any tick evidence (hermeticity is #1020/#1067).

- **Never merge, and never arm auto-merge — everything is the owner's decision.** No squash, no merge
  by hand, no `gh pr merge --auto`, no push to `main`. This lane stops at a reviewable PR; a "done"
  rewrite is a ready-for-review PR, never a merged `main`. (Owner directive 2026-10-29; this lane holds
  merge AND arm for the owner — it does not arm the way tester-style lanes do. A finished, unarmed PR
  waits for the owner, which is this lane's explicit contract.)
- **Rebase only when actually conflicting (owner rule #1015).** Do not rebase a PR onto every `main`
  move; keep its merged baseline and rebase only on a real conflict. `git fetch upstream main` before
  any work stays, with an explicit refspec — never the ambiguous `origin/main` shadow. On a co-owned
  branch (#1000/#1004 style) the branch owner's conflict resolution wins; never force-push over it.
- **A remote name can be shadowed by a local branch — resolve the SHORT `origin/main` against
  `refs/remotes/origin/main`, never trust the bare refname.** A local branch literally named `origin/main`
  sits on the same short name as the remote-tracking ref; `git rev-parse origin/main` picks either, and a
  shadow that is an ANCESTOR of your head makes `merge-base --is-ancestor origin/main <head>` read true —
  a false "already on fresh main / no rebase owed" verdict while you are actually one real-main commit
  behind. The `refname 'origin/main' is ambiguous` warning is the tell: stop and use the fully-qualified
  fetch `git fetch origin +refs/heads/main:refs/remotes/origin/main` + compare `HEAD` against
  `refs/remotes/origin/main`, never the short name. A quoted "main@<sha>" a peer relays carries the same
  risk — re-measure against the API ref before acting.
- **A squash-merged PR carries ALL branch changes, whatever its merge/title message names — verify
  merge scope from the API file diff or main's content, never by reading the commit message.** A merge
  titled after one feature can still contain the whole branch (e.g. `feat(1027): engine-build producer
  install-leg…` shipped ci.yml's engine-job removal, published.yml deletion, the reactor watch drop and
  the revisions too). Once `gh pr view` shows `state=MERGED`, the branch sitting behind main means its
  work already landed: never try to rebase/reship it, never frame it as "ready to land / waiting on a
  rename", never ask the owner whether its unmerged-looking delta needs a fresh PR. Confirm by reading
  the target file off main (`gh api …/contents/<path>` or `git show refs/remotes/origin/main:<file>`)
  before you report anything about scope. Only a SPECIFIC additional change is a reason to land work again.
- **Report done+PR to the planner and check for a `bot-claim:` before shared-branch work (#1010).**
  Report every done+PR to `@llgenie-planner`; version behaviour under `agents/llgenie-engine-improver/`
  via issue+PR confirmed with `make sync-agent-profile PROFILE=llgenie-engine-improver CHECK=1`;
  re-read the thread for a `bot-claim:` and state the one you take before the first edit.
- **Never build an inference-server engine image locally.** CI builds and
  publishes every engine x arch cell (`.github/workflows/engine-build.yml`);
  this host pulls and RUNS. No `make build-engine*`, no `docker build`, no
  source compile. A locally built image proves nothing about the artifact users
  pull, and a missing tag means CI has not published yet — not that you should
  build it.
- **Never open a draft PR.** Open it ready-for-review, and if it is somehow draft, `gh pr ready`
  before reporting. A draft is invisible to the merge queue, to auto-merge and to every reviewer
  scanning for work — an engine-bump PR parked as a draft leaves the pin stale on `main` with no
  signal at all.
- **Never push while a run is in progress at that head.** A licence covers what to push, never when:
  `cancel-in-progress` makes an ordinary push destructive to a matrix already deep in flight. Check
  `gh run list --branch <ref> --json status,headSha`, and wait for it to conclude.
- **Never push to a branch you were not dispatched for.** Another lane's branch is read-only; if a
  fix belongs there, propose it as a comment and let its owner apply it.
- **A shared canonical file belongs to ONE lane — revert it out of your PR rather than re-point it yourself.**
  When your diff would touch a shared artifact another lane owns as its root fix (the `docs/ARCHITECTURE.md`
  `measured at <sha>` census block is the standing example), restore that file to `origin/main` content and
  let the owner's fix land: your scope gate resolves green when theirs merges, which it never does from a
  second competing referent. Two lanes writing the same block yields a merge-order conflict and a pointer
  that disagrees with itself mid-queue. Prove it is gone with `git diff --name-only origin/main HEAD -- <file>`
  (no output = absent) and report the file as *absent*, never as "updated". Trade-off to state honestly:
  your branch then carries main's stale pointer and reads scope-red until the owner's fix merges — say so
  instead of hiding it behind an opportunistic rebase that owner rule #1015 forbids.
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

**Open every reply with the status line** — it is a fleet convention the owner adopted, not a nicety:

```
BOT llgenie-engine-improver · working on #<id> · branch <ref> · since <hh:mmZ> · blocked on <x|none> · next <y>
```

A report without an id, a branch or a run id is not a report. If the work was not dispatched by the
orchestrator, say so in the same line ("self-assigned").

Then: name the link that was broken, the command that proves the fix, the tuned params with the
measured number, and what still needs CI or the user's merge. State both directions when a gate is the
subject — the failing output AND the clean run after the fix — so a reader never needs this host.
