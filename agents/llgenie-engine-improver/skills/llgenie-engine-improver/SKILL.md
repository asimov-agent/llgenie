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

## When to Use

Load this for ANY work on LLGenie engines: a new trending engine that needs a
skill/params/image, a rebuild or build failure, a serving-speed tuning question,
a "model missing from the trend list" report, or a change to the picker/selection
logic. It is the default frame for this profile's sessions.

Versioned copy: `/home/asimov/repository/git/llgenie/.hermes/skills/llgenie-engine-improver/SKILL.md`
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
cd /home/asimov/repository/git/llgenie && git status --short && git log -1 --oneline
cd /home/asimov/repository/git/trending-local-llms && git log -1 --oneline
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

When the change is about which tests run in `ci-unit` vs a dedicated network/probe pipeline:

- **Reuse the existing seam, never reinvent the selection.** Before writing any `pytest -m
  "<marker>"` step, grep the tree for that marker and a make target that already runs the marked set:
  the marker is likely ALREADY registered in `pytest.ini` (ci-unit deselects it with `-m "not
  <marker>"`) and a `test-unit-<marker>`-style seam already runs it through the repo's own discovery
  (`scripts/unit_tests.py run --marker <name>`, containerized). The lane that owns the unit gate owns
  the marker + deselect; you only consume the set. A bare `python3 -m pytest` in a workflow fails —
  the venv/image are provided by the `make ci-<job>`/`make test-*` target, not by the runner.
- **A routing decision is a claim until a test pins it.** When you decide which tests are owned by
  the network pipeline (real opens) versus hermetic, add a hermetic test that asserts the exact
  `@pytest.mark.<marker>` membership across the routed files (marked set == a named allowlist) and
  that no file outside it carries the mark. Then it cannot silently drift either direction (a
  hermetic test losing coverage, or a real one escaping the gate).
- **A host-scanner census is defeated by the model-dict pattern — the exact-equality pin is the
  net, not the scan.** A real Hub call like `mp.download(model, …)` or `mp.gguf_files(model["hf"])`
  carries NO literal `huggingface.co` on the line: the host is implied by the model dict's `hf` key.
  A literal-host grep undercounts (caught live twice on #1000), so rely on the membership pin that
  reds when the marked set != every mark actually in the file — it flags the test a host scan
  could not see. When a teammate's review adds a real mark your census didn't predict, verify the
  test is genuinely a real open, then enshrine it in the pin (do not argue your undercount).
- **A workflow's red must route somewhere; BOTH a roster row and a #349 exemption satisfy the gate.**
  `check_workflows.py` treats `covered (roster row) or exempt` identically — the dated, reasoned
  exemption file IS the routing (security-scan is the live exempted precedent; a red routing nowhere,
  no roster AND no exemption, is the defect). The CI lane owns the choice and can flip it once they
  read the gate's code — do not encode "roster over exempt" as law. Match their CURRENT ruling and
  pin it with a test: if exemption, the entry is dated, names the workflow by exact top-level `name:`,
  and its `reason` says WHY the red is acceptably-routed (the real-call-fake/scan class), like
  security-scan's. A first-time live pipeline can validly be exempted with a stated reason.
- **An owner's "another pipeline" split is two PRs, not one reshaped PR.** When the gate-mechanics
  refactor (#1000: marker + deselect + liveness make targets) and the standalone pipeline (#1002:
  the workflow file) are separated, keep #1001 to mechanics and deliver the workflow as its own
  stacked PR. A workflow that depends on the seam's make targets must STACK on the seam branch
  (cut the worktree from it, base the PR on `main` — the diff collapses once the seam merges), or
  the admission Flow-target check reds on targets the base main doesn't have yet. Give it the owner's
  trigger (`push: branches: [main]` = merge-to-main) plus nightly + dispatch, no `pull_request`.
- **Never run the full hermetic suite on a tree you are still editing.** A mid-run edit to a test
  file the suite will read produces an artifact `usage`/collection failure that looks like a real
  red. Settle the tree, start the suite, and do NOT edit it until it returns; run parallel work on
  a different worktree. If you edited mid-run, kill it and start clean rather than trust the result.
- **Removing a workflow job (or a whole workflow) is a tree-wide cascade, not a one-file edit.**
  Before deleting a job, grep the repo for the job's label AND the workflow's filename. Then reconcile
  every hit in the same change:  shape tests assert `jobs["<label>"]` directly (KeyError the moment it
  vanishes), publish-order/install tests pin the stage's matrix/`none`-row/steps, `run-failure-reactor.yml`
  may list the workflow's `name:` under `workflow_run.workflows` (`make check-workflows` reds with
  "watches a workflow that does not exist"), any test that reads the removed file FileNotFoundErrors, and the
  wiring layer has its own greppable surface: `tests/fixtures/host-only-wiring.json` must record a test the
gate no longer reaches as a host-only document, and any `WORKFLOWS = ("ci.yml", "pipeline.yml", …)`
  enumeration tuple (e.g. `test_pipeline_timeouts`) must drop the removed workflow. When the change kept
  a gate's derived data attached to the registry (a cell enabled / a tag-computation change), regenerate the
  committed tables with their make target (`make render-engine-skill-gap`, `make sync-quant-catalog`, which
  also syncs `tests/fixtures/`) rather than hand-editing — the gate asserts the committed file matches the
  generator. When the stage's behavior has a new owner (e.g. an engine install-test moved into the producer workflow's
  single build job), RE-POINT the tests at that owner's structure — never resurrect the removed labels.
  Distinguish change-caused reds (KeyError/FileNotFoundError on the removed label/file) from genuinely
  external ones. Do NOT label a red "pre-existing" on a hunch — prove it: run that exact test on a clean
  `git worktree add --detach <path> origin/main`; green-on-main + red-on-your-branch means it is YOUR
  regression, not a cancelled sweep or a data drift (both "obviously external" reds have turned out to be
  branch-caused this way — the fix is the cause, not a mangled shape test).
  - `tests/fixtures/host-only-wiring.json` has TWO sections: `documents` records a TEST FILE reached only
    by a CI-never-ran target; `targets` records a MAKE TARGET whose `##` help still claims CI coverage that
    a removed CI job no longer delivers. For the targets side, EITHER reword the help to drop the CI claim
    (the wiring test then accepts the host-only target) OR record it — do not leave a `##` line saying "CI
    engine stage" on a target ci-unit no longer runs.
  - A TARGET + SCRIPT left fully orphaned by the removal (nothing CI-runs calls it and no test references
    it) should be DELETED, not recorded as host-only — the wiring checker asks for deletion and a host-only
    entry for a dead path just papers the rot. Remove the target rule, its entry in the enumerated
    target-list line, any dangling comment mentioning it, and the script; `rg -l <name>` to confirm no
    workflow/test/fixture still references it before you push.
  - An ENABLED backend cell (flipping a variant off its `cpu` fallback) ripples the variant-want maps and
    row censuses AND the derived arch catalog across several test files in ONE change, not just the first
    that reds: the `<engine>-<arch>` variant wants in `test_engine_skills` AND `test_trend_pick`, the
    proven+exempt row census in `test_engine_gate_strict`, and the `arch: [...]` lists in
    `data/trending-quant-catalog.json` + its synced fixture (run `make sync-quant-catalog` after the data
    edit so the fixture matches). Grep the whole tree for the variant before you ship the enable. A DISABLED cell is
    the MIRROR: dropping a variant (e.g. `llama.cpp-prism` cuda off for #103) makes the committed quant
    catalog list an `arch` that `engine_ids()` no longer reports, so `test_every_model_and_engine_is_real`
    reds — refresh the catalog to the DISABLED-aware generator (`make sync-quant-catalog` regenerates
    `engine_ids()[eng]["variants"]`, so `check-quant-catalog` OK is the proof it is DATA-TRUTH not a
    weakened assertion), and edit BOTH `data/trending-quant-catalog.json` AND
    `tests/fixtures/trending-quant-catalog.json` (the exact-match fixture reds otherwise).
    The SAME disable ALSO re-picks the ENGINE in the trend-list matrix — a model whose best cuda engine
    was the disabled PrismML-fork falls back to `llama.cpp` at a much lower tps (the regen records it);
    that tps swing (e.g. 128→6, where a cpu variant would be 128 and faster) is an ORDERING decision
    (arch-match vs best-throughput), NOT an admission bug — file it as its own issue rather than
    revisiting the correct #103 disable inside the feature PR (keep the PR scoped to one concern).
- **Before blaming a code change for a `linux / unit` red, confirm the test is actually IN the gate — a
  direct `python3 -m pytest` run on a live/metal-only file is NOT the gate.** The hermetic unit suite's exact
  selection is `python3 scripts/unit_tests.py argv` (every `tests/test_*.py` minus the `tests/fixtures/unit-suite.json`
  `excluded` and `deselect` entries, minus network-marked). Live-GHCR published-image tests and native-Metal-only
  tests fail on a bare x86 host whether or not the gate runs them; when they are excluded/deselected from the suite
  they  never red `linux / unit`. Run/read the gate `argv` (and the job's actual status — an `in_progress` job is not a
  failure) before writing a regression; a branch that never dispatched the producer to publish its pins leaves the
  live published-image tests red for a reason no code change fixes.
- **A pty/subprocess test must set the SAME env var its code READS — a helper that forces one value while the
  process reads a different env (or the real host) is the flake, not the test's assert.** `mp.system_ram_gb()` reads
  `LLGENIE_SYSTEM_RAM_BYTES` (else the real `/proc/meminfo`), so a pty `_env` that only sets `LLAMA_RAM_BYTES` (a
  name the picker never reads) leaves the process machine-dependent: its row set then differs from the test's
  fixed-64 expectation by exactly the rows whose `system_ram_min` sits between the two, and the test reds (list count
  62-vs-63, reprompt range `enter 1-41` vs `enter 1-42`) without any product change. Pin the var the process actually
  reads in BOTH the harness env and the expectation recompute; when a pty test's count differs from its own `_offer`
  recompute by one row, the RAM/arch seam is the first suspect, not the list code.
- **A test that passes on clean main but reds on a rebased branch usually PINS A STATE MAIN MOVED PAST, not a
  regression in your change.** When you take over a branch rebased onto newer main, run the red test at the branch's
  PARENT before your own commits (a detached `git worktree add --detach <path> <parent-oid>`) to attribute: if it
  fails there too, the branch lineage pins an old expectation (e.g. a cell main enabled — `llama.cpp-prism` "cpu,
  disabled" when the cuda cell is now enabled). Update the expectation to the current enabled reality (the code is
  correct; the test carries stale pre-enable state), and the parametrized sibling rows must change in the same patch.
- **A tag/params change is whole-fleet, so defer the whole fleet — a registry gate that defers only
  params-changed engines reds on every tag.** Enabling a cell or touching a tag-computation source
  (e.g. `scripts/engine_image.py`) re-tags EVERY engine to a new, unpublished hash while leaving the
  params files untouched; a live `wait_published` / publish-order gate then fails across all of them at
  once. Fix the defer logic to treat a change to the tag-computation source like a params repin: defer
  defer every engine to its producer publish (and make the hermetic counterpart assert BOTH the stable-tag case
  and the re-tag case), rather than re-writing the live test to "expect" the missing tags.
- **A `linux / unit` job is COMPOSED: pytest THEN gate steps — a red is the FAILING STEP, not necessarily a
  test.** Read the job log: the pytest summary can be green (`15025 passed`) while a later `make` step in the
  same job reds it — `openspec-tasks-check` (an unchecked openspec task checkbox), `check-docs`, the census, or
  `check-secret-output`. Grep the log for the `N passed` line AND the failing step (`openspec-tasks] FAIL …`,
  `[issue-bot-gates] FAIL …`, `ci-unit Error 2`); never read "unit=failure" as "a test failed" without both.
  The `scope` check red is often the SAME `openspec-tasks-check` failure (the scope job runs it), so ONE
  checkbox fix greens `linux/openspec` + `scope` + the unit job together. Tick a task checkbox only for a task
  whose stated evidence you have — run the promised command first; `openspec-validate` checks the spec TEXT,
  `openspec-tasks-check` checks the BOXES (it fails on ANY unchecked box in a changed change), and
  `make openspec-tasks-check` locally (RC=0) is the pre-push proof. A ticked-but-false task is the exact class
  the gate exists to catch — leave a not-done task unchecked and name it.
  When the suite IS green at a head, re-tick that box in a **SEPARATE commit** whose message cites that
  green run id + `completed_at` — never in the same commit as the code/marker change. The tick's sha must
  be a fact about a green run at that head, not a hope attached to an untested push; a false tick has
  cost this fleet more than once. If the tick's commit message later cites a head where the test was RED
  (the fix landed AFTER the tick), do NOT `git commit --amend` that ANCESTOR to rewrite the citation —
  amending rewrites EVERY descendant sha, so the run id you cite becomes a dangling sha for a superseded
  head. Record the provenance in a PR COMMENT (the green run id + which subsets the old citation
  covered) instead; the state is already correct, only the citation needs correcting, and a comment
  carries it without a history rewrite. But note the chicken-and-egg: `ci-unit` runs `issue-bot-gates`→
  `openspec-tasks-check`, so an UNTICKED box keeps `linux/unit` RED — there is no green unit run at an
  un-ticked head to cite. So validate the box's claim with TARGETED pytest runs at the fixed head (the
  exact tests it promises, e.g. `-m network` → 2 passed), tick there, and the CI unit greens BECAUSE the
  suite is genuinely green — not because the box was unclicked; "unit green THEN tick" is unreachable. And note the PR head can be stale: a commit you made but never pushed
  leaves CI running the pre-fix code at the OLD sha (a check-runs query answering there is the tell) —
  after every commit, push, then `gh api repos/<upstream>/pulls/<n> --jq '.head.sha'` must equal the new
  commit before you read any verdict.
- **A local `make test-unit` red is NOT the CI gate — the same suite in CI can be fully green.** This tree has
  real-HF-call tests (`test_pick_full_registry::test_pick_matrix_real_quant_links_exist`) that are NOT
  network-marked (on main too — the #1000 class), so they fail on a host without Hub access while the CI pytest
  passes (`15025 passed`). Read the CI job's OWN `N passed`/`N failed` summary before treating a local unit red
  as a branch defect; only a CI-pytest failure that is NOT the unmarked real-call test is a real regression.
- **A new test file must reach `scripts/*` through the conftest seam, never its own `sys.path.insert` +
  bare import.** The import-roots ratchet (`scripts/check_import_roots.py ratchet`) reds a file that adds
  its own root with `bare: N+1 vs N` / `sys-path: M+1 vs M`; `tests/conftest.py` already puts `REPO_ROOT`
  on `sys.path`, so write `from scripts import model_engine_pick as mp` and drop `import sys` if it
  becomes unused. A branch cut before that convention writes the old style even when you only added a
  test to an existing file — the ratchet counts the whole merged tree, and the `+N` is usually the one
  NEW file on the branch (files already on main keep main's seam through the 3-way merge). Fix is
  editing the import lines, never a rebase: the PR is mergeable, this is a stale-base style artifact,
  not a conflict. Pre-check on the tree CI actually runs — `git merge-tree --write-tree origin/main
  <fork-ref>` → extract → `ratchet` (**not** `check`, which is the unfiltered report that reds on clean
  main) — and read the pytest summary separately from the gate step, because a `linux / unit` FAILURE can
  be `15046 passed` plus this ratchet `Error 1`.
- **A test whose verdict depends on LIVE upstream data is `@pytest.mark.network` — CLASSIFY it, do not
  pin a duplicate fixture.** `pytest.ini` defines the marker as "a test that calls the real Hub for real …
  EXCLUDED from ci-unit by `-m "not network"`"; a test that downloads the live registry (a `live_sync`
  fixture) or asserts on live upstream runs belongs in the network pipeline, not the hermetic gate. The
  fix is to ADD the marker (assertion unchanged); pinning a snapshot for the hermetic gate just duplicates
  what the live pipeline already runs for real. A test whose verdict moves when someone publishes a
  benchmark upstream is not a regression test. Prove the split: `pytest -m "not network"` deselects them
  and the rest pass; `pytest -m "network"` collects exactly them. And note **`scripts/unit_tests.py` defaults to `-m "not
  network"`**, so a bare `pytest <file>` WITHOUT `-m` EXECUTES the network-marked tests directly and can
  red on live upstream data — a reviewer's "control" that runs `pytest tests/<file>` with no `-m` is not
  running the gate, and its red may be live-data, not a branch defect; always state the `-m` mode you ran.
- **Thread a parameter across call-sites OUTPUT-NEUTRALLY — and quote the criterion before you move any
  expectation.** Making `fits`/`trend_list`/`rank_models` take `arch` must not reorder surviving rows:
  prove it with an A-vs-B run (`trend_list(reg,gb)` vs `trend_list(reg,gb,arch="cuda")`) — surviving rows
  keep identical order, only MEMBERSHIP changes (an Apple-only row drops = the authorised admission
  change). When a test's expectation then differs, decide by the criterion's own words, not preference:
  quote the sentence that authorises the change (e.g. "the card's list is the published tier-local
  ranking") before editing, and NEVER rewrite an assertion to match new output without it. An incomplete
  threading shows up as a product inconsistency (`rank_models` takes `arch` but drops it calling
  `trend_list` while `recommend` threads it) — fix the product call-site, then a broad regression run
  confirms no collateral. The matching TEST call-sites must thread the SAME value the product uses (`fits(…,
  arch=backend)` where `offer` passes `backend`), not a bare `fits` that counts every run.
- **A test's oracle must parse the SOURCE independently, never call the product's own function — and prove
  it discriminates.** An order/selection oracle that calls `mp.tier_tables()`/`mp.card_order` agrees with
  the code by construction (rubber stamp). Parse the README/generator output yourself, and prove it is not
  vacuous: force the OLD expectation (e.g. the global `readme_order`) and show the test goes RED — if it
  still passes, the oracle tests nothing.
- **Before calling a fit assertion a defect, quote WHICH run admits the model (`ran_on` ≤ card).** A "27B
  cannot fit 8 GB" assumption is false when the registry carries a genuine run on an 8 GB card (an RTX 4060
  8 GB, or a MoE/partial-offload build in `4GB VRAM + 32GB system RAM`); `card_evidence="run"` names the
  mechanism but not the row — list the admitting runs (`ran_on_gb` ≤ gb) and quote the hardware string
  before ruling a live-data assertion stale vs a product bug. The stale part is often the test's hardcoded
  absence, not the gate.
- **A branch-vs-main red is a DIFFERENCE, not a verdict — a sibling INVARIANT test decides which side is
  stale, never "main passes".** A behavior-changing PR (e.g. #669's measured-evidence admission) is
  SUPPOSED to differ from main; a same-fixture control showing main-pass/branch-fail proves the change
  happened, not that it is a bug. Before "fixing the product to match main," run the proposed change and
  watch the sibling invariant: the README's own tier table is the #669 admission contract, and
  `test_every_model_the_published_tier_table_places_is_admitted` ("every model its `Up to N GB` table
  places is admitted by `fits(model,N)`") REQUIRES a model the table PLACES to be admitted — so a test
  asserting that model's ABSENCE is the stale side. If making the red test pass (restoring main's
  `vram_min` admission) BREAKS the passing invariant test, the code is RIGHT and the TEST is stale: fix the
  assertion (quote the README placement / criterion that authorises the new expectation), not the product.
  Two tests that contradict (one asserts absence, one asserts admission) are resolved by the authority only
  one of them cites — the README/criterion. Never "fix the code to match main" when a passing invariant
  test proves the code correct; and revert any speculative product fix the moment an invariant test reds
  under it (the `weight > run_card` offload reject was tried, broke `test_every_model…`, and was reverted —
  the test, not the gate, was wrong). **When you correct a stale assertion, move the invariant it
  ACCIDENTALLY carried into its own hermetic (cached-fixture) test.** An `is None` for a model was also
  implicitly asserting "this model is too big for the card"; once the model is (correctly) admitted, keep
  the "a genuinely-too-big model is refused at 8 GB" check as a separate hermetic case rather than
  losing it with the rewrite — correcting the assertion must not delete the real check it was carrying.
- **One PR, one concern — an orthogonal refactor gets its own issue, never folded into the feature PR.**
  A #669 admission/order change must not also thread a multi-function README seam or fix an unrelated
  `rank_engines` variant-normalisation bug; those are real but folding them makes the feature PR
  unreviewable at the moment review matters and mixes unrelated failure modes. File them as separate
  issues with their own acceptance (the forced-old-order red proof, a regression test with the exact
  offending row) and keep the feature PR tight.
- **A stale committed derived fixture reds a mass of parametrized tests at once — regenerate, do not debug the
  product.** `tests/fixtures/trend-list-matrix.json` is DERIVED: after a branch's `trend_list`/registry change it
  is stale, and `test_trend_list_matrix::test_trend_list_matches_the_committed_matrix[...]` fails for many
  (arch, vram, ram) cases at once (e.g. 93, or 17 cuda cases when the arch-aware gate later altered `trend_list`).
  Fix with `make render-trend-list-matrix` then `make check-trend-list-matrix` green, and COMMIT the regenerated
  fixture — never hand-edit it, and never read the mass of matrix failures as a product bug. **Verify the regen's SCOPE before committing a large diff**: diff the old vs new fixture per-case — every changed case must be the TARGET arch (0 non-target rows moved), the admitted model SET unchanged (0 models added/removed), and each changed row the expected mechanism (quote 2–3 before/after). A big diff (e.g. 231+/231−) is legitimate when it is only the target rows re-picked; a diff that also moves a non-target arch row is unrelated drift — call it out, never sweep it in. Two operational
  traps: (1) the render (~37 s) plus the matrix test (~40–110 s) are SLOW — a single foreground command that runs
  stale-check + render + re-check exceeds a 180 s tool timeout MID-render, so the fixture is never written
  (`git status` empty) and it looks like the render produced no diff; run `make render-trend-list-matrix` ALONE
  with a generous timeout, then run the matrix test on its own; and (3) the render walks the live Hub PER MODEL
  (`trend_rows`→`_hub_json`) and 429s HARD on a cold cache — a default `HUB_CACHE_TTL=3600` re-throttles it into a
  timeout that never writes the fixture. Set `LLGENIE_HUB_CACHE_TTL=86400` (a day-long disk cache) so the prior runs'
  fetches persist and the render COMPLETES (`wrote 81 cases`), and run it in the background with notify when the Hub
  is cold. Only then fold the regenerated fixture in and re-run the matrix test. The regen's live-Hub dependency is
  itself the #1020/#1067 non-hermeticity — it hits the regen, not just the tests. (2) A CANCELLED/queued/superseded unit run never
  surfaces this — the stale-fixture reds appear only in a COMPLETED `linux/unit`, so a stream of cancelled unit
  runs at successive heads is NOT evidence the fixture matches; confirm with a local matrix run or a completed
  unit before declaring the derived tables green.
- **The project FORBIDS skip/xfail — an honest interim is a RED, not a marker — and a code change that moves
  product output makes its derived golden red.** `AGENTS.md` states "A skipped test means a broken prerequisite
  is being masked … never leave a skip", and `pytest.ini`/conftest turns any `xfail`/`skip` into a FAILURE, so a
  plan that says "xfail the test until the fix lands" is not executable in this tree (it does not exist as
  policy). When a fix intentionally changes a product output (e.g. the classifier default relabels 77 matrix
  cases), the committed golden can only go green by REGENERATING — and regenerating before a dependent fix
  lands BAKES the known defect into the expectation (a golden that records the wrong behaviour, which the next
  lane then "fixes" by regenerating again). The rule: do NOT regenerate to green when the regen would encode a
  known hole, and do NOT xfail; the code change is a RED pending PR until the dependent fix lands, then
  regenerate ONCE with both fixes. Split the independently-green parts (a gate, a real-data regression test)
  into their own clean PR and carry the golden-coupled part with the dependent fix. **The GREEN-able honest interim is a CANARY test, not a skip:** when the regen is permitted but the dependent fix has not landed, add a test that asserts the defect is PRESENT (e.g. `n > 0` ternary rows on plain `llama.cpp`) whose failure message says 'delete this canary + the PR-body paragraph when the fix lands' — it passes now, REDS the moment the routing lands, and is NOT a skip/xfail; and when the PR body documents the known-defect rows by name (the tracking issue + the correct-routing dependency), the REGEN IS PERMITTED — a golden describing current behaviour that says which rows are known-broken is honest, silence is not. Before splitting, confirm
  WHICH rows the change moves: main's fixture + your fix reds exactly the affected cases — a broad diff is the
  signal to force the regen, and the amount (e.g. 77 of 83) tells you the change is golden-coupled, not a local
  test edit.
- **A family of PRs from one lane can live on DIFFERENT remotes — verify each head via the PR's own
  `pulls/<n>.head.sha`, never `git ls-remote` of a branch name.** An engine-family PR opened from a fork
  (`andyholst/llgenie`) is pushed to that fork's branch; pushing the same branch name to the upstream
  (asimov-agent) either rejects or creates a second, unrelated STALE branch there, and the PR still reads the
  old head. After each push, `gh api repos/<upstream>/pulls/<n> --jq '.head.sha'` must equal the new commit —
  if it does not, the push went to the wrong remote (see the Step 3b fork-publish note). A commit you made
  but did NOT push leaves the PR at the old head while CI runs the stale code — after every commit push,
  then re-read the head; a stale head dimension is a process error, not a CI verdict.
- **A ci/pipeline/engine-job removal is not proven by the touched-files run — run the FULL `make test-unit` gate locally before it is called green.** The tree-wide blast (host-only-wiring documents/targets, a `.PHONY:`-parser corruption, the `trend-list-matrix`/`quant-catalog`/`engine-skill-gap` derived fixtures, row censuses) surfaces ONLY under the complete gate, not the subset of test files you edited; the first full run after a wide change turns up the wiring/matrix/census reds the touched-file run hid. The user wants the local gate actually EXECUTED (not reasoned about) before "green" is claimed — ~20 min / 14.8k tests, worth it.
- **A stale local `origin/main` misleads every base/env-dependent test, so `git fetch origin main` fresh before judging one.** The whole-fleet tag-source deferral fires against an old local main that lacks the tag-change, while CI's current main (which has it merged) sees no defer — a concrete published-image test can then pass locally and red in CI for a base-state difference, not a code bug. On a base-relative test (the deferral, `origin/main`-keyed fixtures, publish-order), re-fetch first; and when the live registry genuinely lacks the pinned tag, the gate stays red until the producer publishes it — no code change moves that, so say so instead of chasing it.
- **A break in a `.PHONY:` multi-line continuation is a TREE-WIDE "not declared .PHONY" red, not 150 missing entries.** Appending a new target as `… test-engine-install \\ ci-install-product` (a space after the continuation backslash) breaks the `\`-newline continuation, so make treats the next TAB-prefixed line as a recipe and only the FIRST `.PHONY:` line's targets parse — every other target suddenly reports "is not declared .PHONY" (28 parsed vs 150) and wiring/phony/issue-bot-gates tests red in a mass. Add the new name BEFORE the trailing `\` and keep the backslash the last char of the line; a huge "not declared .PHONY" list is a parser-corruption symptom, not each target needing an entry. A `make -n <target>` dry-run shows the resolved recipe and catches this before you push.
- **A new ci-install* / product-install stage that builds the repo's pinned python venv runs in the `$(ENGINE_TEST_RUN)` test container, NOT on the bare runner.** The hosted ubuntu runner carries only the distro python (3.12); `make venv-install`/create-venv needs the repo's 3.11, which lives in the `llgenie/test` CI image (pulled by `make test-env`). A product-only install that runs `venv-install`/`link`/`smoke` directly on the runner fails "Python 3.11 was not found" (exit 2) — wrap it in `$(ENGINE_TEST_RUN) sh -c '…'` (Darwin keeps the direct venv branch) like every other ci-install stage. This is why CI broke on a change that passed locally: the test container provides the python the bare host lacks.
- **`git add -A <paths…>` that includes an index-deleted path runs rc=128 and stages NOTHING, silently.**
  The follow-up `git commit` succeeds anyway with whatever was ALREADY staged, so the push can look right
  while your intended edits stay uncommitted. Stage files explicitly one at a time (`git add -- <file>`)
  and read `git status --porcelain` immediately before committing; after the push, `git show --stat HEAD`
  to confirm the intended files are really in the commit.
- **Run a new test to GREEN before you push it.** A pinning test whose assertion form is wrong reds
  at the moment you least want it (caught mid-write this way); run the file, fix the comparison,
  re-run to green, then commit.
- **A new `## ` make target must be documented or be deliberately internal.** Giving a target a
  `##` help line makes `check-docs` require it in docs/ (or a docs-exceptions entry). An internal
  seam carries no `##` line (the `engine-matrix-pushed` precedent); regenerate the dispatch table
  from the generator, never by hand.
- **A new `agent-wiki/<date>-<name>.md` must be INDEXED in `docs/changes.d/<date>-<name>.md` or `check-docs`
  reds** (`[changes-index] ERROR: … is not indexed — add docs/changes.d/…`). The changes.d file is ONE row:
  `| <date> | <summary> | [<name>.md](agent-wiki/<name>.md) | <refs> |`. Add the index row in the SAME commit as
  the agent-wiki file — a good doc with no index row is a RED gate, not a finished change.
- **Shared branch that two lanes co-push: fetch, then `git rebase origin/<branch>`, then push
  additive.** Never guess divergence with `merge-base --is-ancestor` (it misreads an amend-vs-
  remote-head shape) and never force-push over a teammate; when the remote head moved while you were
  mid-commit, `git fetch origin/<branch>` and `git rebase origin/<branch>` then a plain push leaves
  your commit on the new tip.
- **A taken-over PR branch is `refs/heads/<branch>`, NOT `refs/pull/<n>/head` — the PR API caches
  `headRefOid` and can lag the real branch, so branching from the PR-ref and force-pushing CLOBBERS
  the branch's newer head.** A rebase lane or a co-push moves the branch ref to a new commit while
  `gh pr view … --json headRefOid` still reports the old one; work based on the stale PR-ref, then
  `--force-with-lease` over the real head, deletes work that is not yours. Before taking an existing
  branch, `git fetch origin +refs/heads/<branch>:refs/remotes/origin/<branch>` and base on THAT ref
  (re-measure with `gh api …/git/ref/heads/<branch>` if in doubt), never on `refs/pull/<n>/head` or
  a quoted sha. If you already clobbered it, restore the prior head (`git branch -f <br> <prior-oid>`),
  `git reset --hard` the worktree to it, and CHERRY-PICK your commits additively on top before the
  lease-push — never re-push a lineage that dropped it.
- **Rebasing onto a main that MOVED A PRODUCT'S OUTPUT ORDER: take main's DERIVED expectation, never the branch's hardcoded one.** A branch cut before a gate change (e.g. the measured-VRAM card gate reordering `trend_list`) hardcodes the pre-change order in its test, while main's copy of the same test DERIVES the order from the source and passes. A `--onto` conflict resolution that takes `theirs` (the branch's side) bakes that stale hardcoded order and reds on the rebased tree — and it will read as a merge artifact when it is really an outdated expectation. Before resolving: run the red test at main and at the branch's parent (`git worktree add --detach`); if main DERIVES and the branch hardcodes, KEEP main's derived form and re-apply only the branch's real additions (the new hermetic twins/tests). Never hand-adjust the expectation to satisfy both sides — re-derive it from the product and quote the product's order (`trend_list(reg, gb, arch=…)` gives the README's tier order) as the authority.
- **A `git worktree add` PATH is relative to the REPO'S OWN directory, not the parent — a "worktree is
  missing" report is usually a wrong-path probe.** `git worktree add -b <br> llgenie-wt/<x> <ref>` run
  with cwd inside the repo creates the worktree at `<repo>/llgenie-wt/<x>`, not the sibling workspace
  path you probed. Resolve the real locations with `git worktree list --porcelain` and probe those
  before concluding a worktree add failed or the edit vanished.
- **A "superseded / close it" verdict is a count against main, not a peer's assertion.** A teammate's
  "everything already landed on main, close the co-owned PR" can be wrong while sounding measured: the
  seam (marker, `-m "not network"`, the pipeline) merges but the ROUTING MARKS do not, so real-call
  tests stay unmarked and run inside the hermetic gate. Before consenting to a close/merge, count what
  main actually carries (e.g. `git show refs/remotes/origin/main:<file> | grep -c
  '@pytest.mark.<marker>'` versus the expected set) and confirm the missing piece is genuinely absent —
  a wrong-but-confident verdict is corrected the same way, by measurement, on the record, not by
  deferring to the claimant.
- **An owner split across a workflow-ownership boundary: agree the shared branch + ONE-PR vehicle BEFORE
  either lane cuts, and opening the ADDITIVE half first is safe only because the removal side is still
  on main.** When one lane owns the engine build/publish path and another owns the workflow files,
  coordinate the branch name and base first. Cutting your additive half (e.g. a per-row producer install
  test) ahead of the counterpart's removal (the consumer tag-poll) is a no-gap shape only while that
  removal hasn't landed on main; never let the removal outrun the addition or install-testing goes
  untested in between. Open the vehicle, flag the counterpart to join, and hold the co-push until both
  halves are queued on the same branch.

- **A file-adding PR's `docs/ARCHITECTURE.md` census pointer CANNOT be made main-ancestor AND
  count-correct at the same time — do not chase it; HOLD THE MERGE for #1053.** The gate uses
  `git ls-tree HEAD` as ground truth, so a file-adding PR must point `measured at` at a sha whose tree
  count == its own head (2009 files) — but no sha carrying those added files is an ancestor of main
  (they don't exist on main until the merge). Pick the PR's own tip → tree-count correct but dangles
  on squash (main re-reds, the #1048/#1052 class); pick a main ancestor → survives squash but its
  count (2002) != the PR's head (2009) → the gate reds now. It is structurally unachievable per-PR;
  that is exactly the gate defect **#1053** fixes (referent = tree-at-named-sha + tolerate the
  file-adding case). So: hold the PR's MERGE until #1053 lands (its unit may show green mid-flight —
  do NOT let it merge and re-break main's `check-docs`), then re-derive once against the fixed gate.
- **Do NOT chase a per-PR `docs/ARCHITECTURE.md` census pointer — it is a GATE DEFECT (#1053), not a
  lane fix.** The census gate (`check_architecture_census.py`) uses `git ls-tree HEAD` as ground truth,
  so EVERY file-adding PR must rewrite the census to its own head + point `measured at` at a sha
  matching it — and that per-PR sha dangles the moment the PR is squash-merged (the same
  dangling-pointer class, now on `main`). The correct fix is the gate's referent = the tree at the
  NAMED sha, not HEAD (issue #1053). So: a file-adding PR that only reds the census gate is HELD for
  #1053, not given a per-PR pointer rewrite; re-verify its unit green once #1053 merges + main moves
  (re-base then). Rewriting the pointer per-PR is a second vehicle that the squash re-breaks.
- **Read `autoMergeRequest` and `pulls/<n>.head.sha` from the API at the moment you write the sentence
  that names them.** Both are writable fields with no history: an arm can be set by an automation acting
  against the lane's charter, cleared by a peer, or re-armed a minute later, and a remembered value is a
  guess. Stale arm reads err consistently toward "calmer than reality" (a PR believed parked is MERGEABLE
  and armed), so quote `mergeMethod` + `enabledAt` from `gh pr view <n> --json autoMergeRequest` before
  any claim about arming.
- **Report the PR head from the API (`gh api repos/asimov-agent/llgenie/pulls/<n> --jq .head.sha`),
  never the sha you believe you are on.** A commit that exists in your tree but was never pushed
  leaves the PR head stale while your local HEAD is ahead — the single largest source of false
  "done" reports. After every push, assert `pulls/<n>.head.sha == $(git rev-parse HEAD)` (it is the
  only check that catches an unpushed commit); if they differ, the push did not land. Also read
  `pulls/<n>.state` + `mergedAt` BEFORE any rebase/catch-up push: a PR you were asked to move can already be
  MERGED (`headRefOid` null, `state=MERGED`) by another lane or the owner — force-pushing its branch then rewrites
  a STALE branch of a merged PR while the work is already on main (verify with `git log origin/main --grep`). Check
  the state first; if merged, there is nothing to catch up — say so, do not rebase a dead branch.
- **A test that makes a real Hub call belongs in `@pytest.mark.network`** (pytest.ini: "a test that
  calls the real Hub for real … EXCLUDED from ci-unit by -m 'not network'", issue #1000) — so the
  hermetic gate never depends on live upstream data. Marking is the fix, not pinning/weakening; the
  assertion stays and runs in the live pipeline. A test whose verdict moves when someone publishes a
  benchmark is not a regression test. When an engine cell is built from a pinned source
  sha rather than a PyPI/installed wheel (vllm, sglang + a prebuilt cell's `runtime_copy`), the
  census/gap row and the `linux/unit` detect must point at a sha reachable from `refs/remotes/origin/main`,
  or the gate reds with the dangling-pointer class (the `bc3859b`/`#1052` shape: a census pointer
  to a sha not on main is un-verifiable). Prove it before merging: `git merge-base
  --is-ancestor refs/remotes/origin/main <sha>` must be YES for every committed sha the build's
  census/detect names. A PR whose head predates the main census-pointer fix keeps its
  `linux/unit` red until main is pulled in (`is-ancestor main <head>` = NO means the fix hasn't
  landed under it) — re-base/merge main, then the unit re-runs green.
- **A generated spec/params/openspec file must end with a newline — `linux/lint` checks it and
  reds otherwise.** A `.md`/engines file committed without a trailing `\n` (e.g. a vllm/sglang
  spec.md) fails the lint-newline check; append the trailing newline in the same change that
  introduces the file, before pushing. The `linux/unit` and `linux/lint` are separate checks —
  confirm each check's completed conclusion separately, never fold one green into a claim for
  the other.
- **The card gate is ARCH-AWARE: a measured run admits a model only on hardware this host can
  reproduce.** An Apple/Metal "unified memory" run (an MLX "M1 Pro 16GB" row beside a "M4 Max
  128GB") is never a cuda/vulkan/rocm/cpu card, so it must not admit the model on such a host; but a
  real run on this host's own arch on a smaller card DOES admit it even above its declared `vram_min`
  (issue #669 — the run wins, `vram_tier` never decides). Thread `arch` through `fits` →
  `card_evidence` → `admitting_measurement` → `trend_list` → `recommend` (default `None` = a bare gate
  call counts every card-sized run, preserving the #669 gate tests; a container arch excludes Apple
  runs, a Metal host counts them). Do NOT "fix" an over-listing by making `vram_min` a hard floor
  before the run evidence — that breaks the #669 run-wins semantics.
- **A retry budget SMALLER than the real backoff window is a fail-fast, not a budget — size it between the real window and the refused cap, and do NOT "allow one wait" instead.** A 429 wait bounded by a total below the Hub's own window raises on the FIRST 429 at "1 attempt, 0 waits, 0 s spent", turning a transient error into a suite failure (a live matrix/pick test reds on the branch while main's un-budgeted retry passes). The fix that works sizes the total to the real window (300 s = the Hub's 5-minute default) while still refusing the pathological cap (600 s), so a transient window is waited out and the 20-minute hop stays impossible. The tempting "always allow the first wait" is WRONG: it sleeps the 600 s cap and breaks the sibling test that pins the cap refused — run that test before choosing the shape. A changed DEFAULT is a doc-truth cascade: `grep` the literal old value and update EVERY place that quotes it (agent-wiki, proposal, spec, docstring, openspec task text), leaving only the test-scenario lines that `monkeypatch` it deliberately.
- **A worktree branch can track a stale/gone remote and carry an UNRELATED commit — verify the branch and your commit's parent before committing or pushing.** A minimal PR fix is the PR's OWN head plus your one commit: confirm `git rev-parse <your-commit>^` equals the PR's `headRefOid`, and check `git log --oneline -3` + `git status -sb` (an `…origin/prNNN [gone]` upstream is the tell). If the worktree was switched onto a local branch that carries another lane's work on a newer base, locate your isolated commit with `git log --all --oneline`, then `git reset --hard <your-commit>` — never stack onto the stale branch or push a rebase nobody asked for over an unrelated history. Cherry-picking your one-file commit onto a newer stale branch drags that branch's unrelated commits into the PR.
- **`pkill -f <pattern>` can kill your OWN shell when the pattern appears in the running command line.** A repo/test command whose script text contains the pattern (e.g. `pkill -f "pytest tests/foo"` inside a compound command that also names that path) matches its own bash process and dies with exit −15 and no output. Use the process tool's kill by session id, or a pattern that cannot match the current command, instead of a broad `pkill -f`.

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
attribution of the failing test legs) is the recipe in `references/agent-profile-soul.md`.

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

- **Every session: check the engine-build pipeline AND the sync pipeline, and fix what is red.** Read the latest `engine-build` runs and separate a genuine failure from a documented gap (#103 build-time libcuda). Read `registry-sync` (the sync from `andyholst/trending-local-llms`) — it is `disabled_manually` today, so the trend list is not syncing; re-enabling is owner-only. When a genuine error appears, **research it (web) before patching** — a current upstream flag/known-issue beats a guess. Known live example: the #1027 install-leg (`make test-engine-install`) fails for EVERY cuda cell because it calls `engine_skills.py install`, which correctly exits 3 for a container-only engine ("installed in its container image, not on the host") — the leg must test the container path (pull/serve/`test-built-engine`), not host install. A cell's image can build + serve green while its install-leg is red; check both.

- **THE CORE LOOP (this lane's whole job): sync → arch → build → offer, and verify each leg.** (1) Sync the trending local-LLM list and trending local inference-server list **from `andyholst/trending-local-llms`** — not hand-edited. (2) Know each engine's **supported arch types** (cuda/rocm/vulkan/cpu/metal) from the sync. (3) For every supported `(engine, arch)` cell, verify it **builds and publishes a Docker image** (`engine-build`); a cell that is "supported" but does not build is a **gap**, and a disabled cell must carry its #103-class reason + a documented fallback. (4) Only then does the picker offer a model+server pair — and only when the run's `measured_on` matches this host's arch and a card it can reproduce. The picker must never offer a pair that (a) the engine cannot load, (b) was never built, or (c) was measured on other/unknown hardware. Detail: issue #1092.
- **`measurement_backend()` defaults to CPU, never CUDA — and changing that default REQUIRES stating the explicit CUDA case.** The classifier returned `"CUDA"` for any hardware it did not recognise, so a `CMF Phone 2 Pro (on-device)` run and an `iPhone 18 Pro Max` run both bucketed CUDA and were admitted as cuda measurements (the `APPLE` regex `apple|M[1-9]|mac` misses "iPhone"). Fixes: `APPLE` gains `iphone|ipad` (→ Metal); `_CPU_HW` gains `phone|on-device|android|galaxy|pixel` (→ CPU); the default becomes **CPU**. THE TRAP: the old CUDA default was LOAD-BEARING — it caught every `_CUDA_HW` token (rtx/nvidia/geforce/tesla/dgx/…) because no branch returned CUDA for them explicitly, so flipping the default silently turns `RTX 3060`/`RTX 4090`/`H100` into **CPU** (a real regression caught only by re-running the table). So add `if any(k in hw for k in _CUDA_HW): return "CUDA"` — plus a generic `\bgpu\b` → CUDA for an unnamed "8GB GPU" (`"no gpu"`/`"cpu only"` are already CPU via `_CPU_ONLY`) — BEFORE the default. Verify against the WHOLE table (RTX/DGX/"8GB GPU"→CUDA, RX/Strix Halo→ROCm, Pi/"cpu only"/phone/unknown→CPU, M5/iPhone→Metal): a phone-only check passes while RTX→CPU ships. Any "measured_on" verdict must be reproducible from the hardware string; a phone is never a cuda result.
- **A build wall-clock / image-size measurement comes from CI, never a local build.** Dispatch `engine-build` for the cell(s); read wall-clock from the job step timing (`gh api repos/…/actions/runs/<id>/jobs --jq '.jobs[].steps[]|select(.name|test("build"))|{name,started_at,completed_at}'`, quoting the run id beside the numbers — a wall-clock without a run id is a claim about time), and image size per cell from the pushed manifest (`docker manifest inspect` / registry digest). A cached `available -> no rebuild` is **not** a measurement: leave the acceptance criterion NOT MET rather than substitute the author's cached number. An honest gap is actionable; a cached number looks like evidence and cannot be told apart from one.

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
