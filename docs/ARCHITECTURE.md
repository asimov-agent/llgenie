# llgenie architecture

llgenie is a local GGUF model launcher with a hardware-aware picker. It does not compile or
run an inference server on the host: it detects the host's backend, pulls the matching
CI-built engine image from GHCR, and writes small start scripts into `~/bin` that run those
images. The picker chooses a model from the vendored trend registry and an engine that the
registry measures for that model on this hardware, then launches it through the engine's
image. The one exception is Apple Silicon: Metal cannot be reached from a container, so the
engines whose skill declares a native `metal` install run on the host.

This document is the map of the shipped path. It is refreshed by `architecture-bot`
(`make architecture-bot-brief` -> `architecture-bot-doc` -> `architecture-bot-publish`)
whenever the tree moves. `make architecture-bot-brief` is what reads the real tree: tracked
layout, `scripts/` modules, `##` make targets, workflow jobs and cron slots, `data/`,
`skills/`, `containers/` and `tests/`, plus the git drift since the doc's last commit.

## The shipped path

1. **Bootstrap** — `make venv-install` builds the Python 3.11 gguf-tooling venv at
   `~/llama-gguf-tools/.venv` (deps from `tools/requirements.in` /
   `tools/requirements-dev.in`, compiled by `make -C tools generate-requirements`).
2. **Backend detection** — `scripts/detect_server.py` resolves the host's tree and backend
   (`metal`, `cuda`, `rocm`, `vulkan`, `cpu`) from the GPU it finds; on a card of 24 GB or
   less the tree is the Prism llama.cpp fork, above it upstream llama.cpp.
   `scripts/engine_runner.py` runs an engine's install / detect / serve steps from that
   engine's frozen params file (backend included). `LLAMA_BACKEND` (or `ARCH=`) overrides the
   detected backend, which is how CI exercises a backend on a GPU-less runner.
3. **Install** — `make install` chains `bash-check -> venv-install -> engine-launchers ->
   link -> test-built-engine -> smoke`. `scripts/install_engine_launchers.py` builds the
   install plan: the engine images this backend needs, pulled from `LLGENIE_REGISTRY`
   (default `ghcr.io/asimov-agent`). It pulls only and never builds (`BUILD=1` is the
   explicit exception); the default plan is the core llama.cpp set, `ENGINES=all` pulls
   every engine, and any other engine is pulled on first use by `llgenie --pick/--engine`
   (`--ensure <id>`). It writes `~/bin/llgenie-engine-<id>` per engine (`--version` prints
   the engine version, `<model> [port]` serves it as `llm-local` on
   `127.0.0.1:${PORT:-11434}/v1`), plus the `~/bin/llama-server` (stock llama.cpp) and
   `~/bin/prism-server` (Prism) shims. `link` writes `~/bin/llgenie` and symlinks
   `~/bin/llgenie.py` to this repo's `scripts/llgenie_serve.py`.
   `make test-built-engine` then runs every start script with `--version` through its image.
   `install_engine_launchers.install_plan` is the single list of tags `make install` pulls,
   which is why `make ci-wait-engine-images ARCH=<backend>` can wait on exactly those tags
   before the CI `install` job runs.
4. **Trend list** — `scripts/model_engine_pick.py` reads `data/models.json`, filters models
   to the ones whose VRAM tier fits this card, and ranks them (`recommend` for plain
   `llgenie`: the upstream README "Most loved" order, with a stated reason on rows that
   cannot be served here; `rank_models` by best measured t/s). `rank_engines` orders each
   model's engines by a figure measured on this host's kind of hardware and card class first
   (`scripts/model_engine_pick.py`), so the engine list is what the registry measures for
   this machine, not a hand-kept list. `scripts/trend_list_matrix.py` renders the same list
   per `(arch, vram, ram)` into `tests/fixtures/trend-list-matrix.json`, which
   `llgenie --matrix` prints and `make check-trend-list-matrix` guards.
5. **Engine skill** — `skills/engines/<id>/SKILL.md` is the one engine description: install
   steps, `container:` blocks per backend (`apt`, `cmake`, base image), the `detect`
   command, and the native `metal` path. `scripts/engine_skills.py` is the generic loader and
   runner (no engine-specific code). `make generate-engine-params` is the only step that
   reads the skills: it freezes each one into `containers/engines/params/<id>.json`
   (one variant per backend x GPU arch) plus `containers/engines/binaries.json`, and writes
   one Dockerfile per engine x arch under `containers/engines/dockerfiles/<id>/`. Registry
   engines with no skill are tracked by `make engine-skill-gap` /
   `make spawn-engine-skill-issues` (`data/engine-skill-gap.json`,
   `data/unsupported-engines.json`).
6. **Engine image** — `make build-engine ENGINE=<id> ARCH=<arch>` builds strictly from the
   generated params and Dockerfile with plain make; `make test-engine` (OpenAI API answers
   on a tiny model) or `make test-engine-image` (version only, for GPU-only images) tests it,
   and `make push-engine` publishes it to `ghcr.io/<owner>/llgenie/<name>` as
   `<pinned-hash>-<arch>` and `:<arch>`.
7. **Serve** — `scripts/llgenie_serve.py` scans `~/models/**/*.gguf`, sizes the KV cache and
   `-ngl` for the card, resolves `llama-server` to the container shim (Prism on cards of
   24 GB or less, like `detect_server`), and serves the OpenAI API as `llm-local`. Metal
   runs natively through the skill's install because a container cannot reach the GPU there.

## Repository layout

| Path | Role |
|---|---|
| `Makefile` | the only entry point for every stage and gate; CI calls `make <target>` and nothing else |
| `scripts/` | all logic: install, detection, pick, engine images/params, registry sync, bots, gates |
| `skills/engines/` | one `SKILL.md` per engine, the source `generate-engine-params` reads |
| `containers/engines/` | shared base Dockerfiles, generated `dockerfiles/<id>/Dockerfile.<arch>`, frozen `params/`, `binaries.json`, `entrypoint.sh` |
| `containers/test/` | the test image every Python gate runs in (no inference server inside it) |
| `containers/agent/` | the pinned Hermes agent image every bot leg runs in |
| `containers/ci-variant/` | the CUDA-toolkit variant-build image (`make test-variant-image`) |
| `data/` | vendored registry, quant catalog, strata model map, engine-skill gap, unsupported engines, trending README |
| `docs/` | this document |
| `openspec/` | the change record: `changes/<name>/{proposal.md,specs/**,tasks.md}` |
| `agent-wiki/` | dated work record, one entry per change, referencing its issue and PR |
| `tests/` | hermetic unit tests, fixtures, and the live end-to-end gates, discovered by `scripts/unit_tests.py` |
| `docker-compose-files/` | the OpenSpec/test image compose definitions |
| `tools/` | pip-compile inputs (`requirements.in`, `requirements-dev.in`) |

## Engine images

`skills/engines/*/SKILL.md` is the source; `make generate-engine-params` is the only step
that reads it, and it writes the frozen params plus one Dockerfile per engine x arch. CI
builds `make build-engine ENGINE=<id> ARCH=<arch>`, tests the image
(`make test-engine` / `make test-engine-image`) and `make push-engine` publishes it. A
published image is pulled back with no build and no cache by `make test-published-engine`,
which checks the digest, the binary version and — for CPU images and GPU images with a CPU
fallback — serves the tiny model and answers "hi".

`scripts/engine_image.py` owns the tags, the CI matrix and the `DISABLED` set (an engine x
arch image that cannot finish in CI is disabled with its tracking issue, never left as a
red job). GPU images never contain a driver: the host driver is mounted through the
container runtime (CDI for CUDA, `/dev/kfd` + `/dev/dri` for ROCm/Vulkan). The skills cover
`llama.cpp`, `llama.cpp-prism`, `llama.cpp-laurentzuijdwijk`, `exllamav3-rocm`, `vllm`,
`sglang`, `ollama`, `mlx`, `mlx-fast-bonsai2`, `tensorfold`, `strata`, `litert`,
`tensorrt-llm`, `freetoken`, `webllm` and `dflash2`.

A weekly `engine-bump` pins each skill to its upstream release, derives the dependency
delta (`scripts/engine_deps.py`) and regenerates the Dockerfiles; `engine-bump-rebase`
keeps those PRs current. A dependency delta the skill cannot absorb is a hard fail that
still moves the pin and still opens the PR — the body carries the finding and CI stays red
until a person writes the install line.

## Data

- `data/models.json` is a **verbatim** copy of trending-local-llms' registry, replaced
  wholesale by the weekly `registry-sync` PR. `scripts/registry_keys.py`
  (`make check-registry-keys`, part of `make check-registry`) fails a sync that loses a
  model, a key, a measurement, a t/s or an engagement counter — the vendored copy is
  additive only.
- `data/trending-quant-catalog.json` is generated from the real registry and the live Hub
  (`make sync-quant-catalog`) and checked by `make check-quant-catalog`.
- `data/strata_models.json` is written from Strata's `setup.py` at the skill's pinned
  commit (`make sync-strata-models`, checked by `make check-strata-models`).
- `data/engine-skill-gap.json` and `data/unsupported-engines.json` are the shipped /
  known-unsupported / new-and-unresolved engine picture (`make render-engine-skill-gap`,
  `make check-engine-skill-gap`).
- `data/trending-README.md` is the vendored upstream README the "Most loved" order comes
  from.
- `tests/fixtures/trend-list-matrix.json` is the rendered trend matrix
  (`make render-trend-list-matrix`, checked by `make check-trend-list-matrix`).

## CI

`.github/workflows/ci.yml` is the entry. Its jobs, exactly as they are declared:

| Job | Role |
|---|---|
| `guard` | the owner/collaborator gate every other job needs |
| `ci-images` | publish the test and OpenSpec images on a new Dockerfile + lockfile hash, never rebuild per job |
| `linux` / `macos` | call `pipeline.yml`, the reusable per-OS verification pipeline |
| `engine-base` | the shared engine toolchain base image |
| `engine-matrix` | the engine x arch matrix the image jobs are built from |
| `engine-image` | one parallel job per engine x backend: build, test, push |
| `engine-published-test` | push runs only: pull every published image back, no build, no cache, and serve it |
| `linux-published` | calls `published.yml`, which runs `make ci-engines BACKEND=<b>` for `cpu`, `cuda`, `rocm` and `vulkan` |
| `auto-merge` | land a green, conflict-free PR (below) |

`pipeline.yml` runs one job per `make ci-<job>` target (`ci-lint`, `ci-unit`,
`ci-agents-read`, `ci-openspec`, `ci-cpu-health`, `ci-top-tier`, `ci-install`), the same
jobs and asserts on both OSes; only the runner label differs. `publish-agent-image.yml`
publishes the Hermes agent image (guarded to owner/collaborators, amd64 only).
`run-failure-reactor.yml` routes a failed run to a fix or a deduped issue.

**`auto-merge` is how a PR lands (issue #482).** It `needs:` every PR-relevant job
(`guard`, `ci-images`, `linux`, `macos`, `engine-base`, `engine-matrix`, `engine-image`,
`linux-published`) and requires each of them to be `success` — a skipped job is not a pass.
It then runs `make auto-merge PR= REPO= HEAD_SHA=`, i.e. `scripts/auto_merge.py`, which
reads one `gh pr view` and squash-merges only when every one of these holds: `state` OPEN,
not a draft, `mergeable` MERGEABLE, `mergeStateStatus` CLEAN, `headRefOid` equal to the
commit this run validated, and no `do-not-merge` label. Everything else is **deferred, not
failed**: the job prints the reason (`DIRTY` = conflicts, `BEHIND` = stale, `BLOCKED` = a
required check or review pending, a moved head, the hold label) and exits 0.

A head in this repository **or** in the owner's fork (`andyholst/llgenie`) is accepted, since
every agent PR is pushed to the fork (issue #488); a fork head is merged **without**
`--delete-branch`, because the base token cannot delete a branch in the fork. The merge is
`gh pr merge --squash --match-head-commit <sha>` run with the owner PAT
(`secrets.BUMP_TOKEN`) — a merge made with the job token starts no workflows, so the
post-merge run on `main` (which publishes the engine images) would never happen. After the
merge `scripts/verify_closure.py` reads the PR's own `closingIssuesReferences` and fails,
naming the issue, when a claimed `closes #n` did not bind. `make verify-closure PR= REPO=`
runs the same check by hand on any merged PR.

The structural gates are make targets, so the same command runs locally and in CI:
`make check-workflows` (GitHub expressions parse, trailing newlines, every workflow has a
`name:`), `make check-dispatch-forms` (a dispatchable workflow documents its inputs and
stages), `make check-wiring` (every script/test reachable from a target CI runs, and every
target that writes no file of its own name is `.PHONY`), `make check-docs` (every `##` make
target is in `README.md`, every `agent-wiki/` entry names its issue and PR),
`make check-pr-hygiene`, `make check-pr-authors`, `make check-secret-output`,
`make secret-scan` / `make secret-scan-self-test`, plus `make bash-check`
(`scripts/check_bash.py`, the bash-5 parity check that resolves the Makefile's shell) and
`scripts/check_python.py`, which `tools/Makefile` runs to keep the gguf venv on Python 3.11.

## Bots

Every bot is a workflow with its own cron slot, its own `concurrency:` group, an
owner/collaborator guard before any secret is read, and a transcript redacted by
`scripts/scrub_log.py` before any of it prints. No bot merges: it pushes the branch and
drives the PR green, and landing is CI's `auto-merge` job (above) or a human's, with
`do-not-merge` as the hold. A bot's run inputs (`issue.md`, `triage.md`, `refine-in.md`,
`refine.md`, `comment.md`) are git-ignored: they are scratch a run writes, never repo
content.

| Workflow | Cron | What it does |
|---|---|---|
| `issue-bot.yml` | `23 6 * * *` | implements ONE labeled/ready issue per run as a reviewable PR. The implement leg carries its own `timeout-minutes: 90` under the job's 120 (issue #476), so a run that exhausts its budget fails its own step with 30 minutes left to salvage the tree — detect the change, commit, push, open the PR. A manual dispatch with no issue number picks one itself, the implementation is measured from the changed tree (not the exit code), and the PR body is built from the run's `pr-body.md` |
| `fix-bot.yml` | `17 * * * *` | the scheduled `sweep` job asks `make fix-bot-sweep` which red PR deserves the bot and dispatches the `fix` job with it; `scripts/fix_bot_sweep.py` considers open non-draft PRs whose head is this repository or the owner's fork (issue #340), not `main`, with a failing check and fewer than 3 `fix(bot):` commits, oldest-updated first, one per sweep. The `fix` job repairs the branch in the agent image, re-runs the gate, and pushes one commit only when it is green (180-minute cap: 3 x (check + repair)) |
| `rebase-bot.yml` | `29 */6 * * *` | drains every eligible PR onto `main` in one run, bounded by `max_prs`; decides from a computed merge state (`make rebase-bot-sweep`), counts a rebase from its `bot-done` marker, aborts a stopped rebase so the tree returns to `main`. After a rebase the structural gates are chained with `&&` and the lint image is supplied, so a failing `make lint` fails the leg instead of being swallowed by the next command's exit status (issue #455) |
| `issue-refiner.yml` | `43 * * * *` | reviews one issue and refines or closes it with cited evidence |
| `code-review-bot.yml` | `31 7 * * 1` | files issues for findings in the tree and the pipelines |
| `registry-sync.yml` | `19 5 * * 1` | byte-copies the upstream registry, regenerates the derived tables, opens a PR |
| `engine-bump.yml` | `53 6 * * 1` | pins every engine skill to its upstream release |
| `engine-bump-rebase.yml` | `41 5 * * *` | keeps the engine-bump PRs current |
| `queued-alarm.yml` | `7,37 * * * *` | reports jobs stuck in `queued` |
| `search-smoke.yml` | `11 7 * * *` | proves the masked web reach works |
| `architecture-bot.yml` | `47 */6 * * *` | rewrites `docs/ARCHITECTURE.md` from the brief and opens one linked issue + PR |
| `run-failure-reactor.yml` | — (dispatch / `workflow_run`) | routes a failed run to the fix-bot or one deduped issue |

Bots run inside the pinned agent image (`containers/agent`), call the model pinned once in
`scripts/agent_model_pin.py` (alias `nous-deepseek`,
`deepseek/deepseek-v4.1-flash-1017`) and are covered by
`tests/test_bot_pipeline_isolation.py` (no shared cron slot, no shared concurrency group).
`tests/test_bot_time_budget.py` asserts the workflows' job and leg budgets against the
loops' own defaults. Every leg runs `scripts/require_env.py` before the image is built (a
missing credential is loud, never a skip), `make hermes-smoke` proves the model can call a
tool, and `make agent-shell-keys-check` proves every forwarded credential is visible in the
agent's own shell. A leg's public output goes through `$(call scrubbed_run,…)`: the raw
stream stays in a gitignored `$(HERMES_LOG)`, and only `scripts/scrub_log.py`'s redacted
tail prints.

## Tests and gates

`make test-unit` discovers every `tests/test_*.py` through `scripts/unit_tests.py`; a file
is in the gate the moment it exists, and an exclusion is a dated entry in
`tests/fixtures/unit-suite.json` (`scripts/unit_tests.py excluded` prints them). `make test`
runs the named `groups.fast` subset (`scripts/unit_tests.py run --group fast`) from the same
roster rather than a hand-kept list of files. The live gates are separate targets
(`test-install`, `test-health`, `test-engine`, `test-published-engine`,
`test-native-engine*`, `test-top-tier*`) and are never skipped: a missing prerequisite
fails loudly. On an Apple-Silicon host `make test-health` is the real GPU/Metal proof — it
launches `~/bin/llgenie` against the host's Metal `llama-server`; on Linux it answers "hi"
through the llama.cpp engine image.

`make loop` (`scripts/loop_harness.py`) chains image -> download -> lint -> agents-read ->
unit -> install -> health -> top-tier -> top-tier-serve -> test -> openspec ->
openspec-tasks -> clean, and fails closed on any stage. `make check-docs`,
`make check-pr-hygiene`, `make check-pr-authors`, `make check-workflows`,
`make check-dispatch-forms`, `make check-wiring`, `make check-secret-output` and
`make secret-scan` are the repository's structural gates; `make auto-merge` and
`make verify-closure` are the two the merge itself runs. The data gates
(`check-registry`, `check-registry-keys`, `check-quant-catalog`, `check-trend-list-matrix`,
`check-engine-skill-gap`, `check-strata-models`, `check-engine-params`, `skills-validate`)
run inside `make ci-unit`, next to `check-agent-model`.

## Adding a change

An issue is the root; the branch, the OpenSpec change (`openspec/changes/<name>/`), the code
and the PR all trace back to it. Work happens in its own git worktree cut from
`origin/main`. The OpenSpec change is written before the code, each task is ticked when
verified, and the README and an `agent-wiki/` entry land in the same commit. The PR targets
`asimov-agent/llgenie:main` from the fork's branch and closes the issue with `closes #<n>`.
The agent never merges and never pushes to `main`: it pushes the branch, drives it green,
and CI's `auto-merge` squash-merges it once the run is green and the PR is CLEAN. After the
merge, `make worktree-prune` removes the branch and worktree whose PR is merged.
