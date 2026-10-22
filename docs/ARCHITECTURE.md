# llgenie architecture

llgenie is a local GGUF model launcher with a hardware-aware picker. It does not compile or
run an inference server on the host: it detects the host's backend, pulls the matching
CI-built engine image from GHCR, and writes small start scripts into `~/bin` that run those
images. The picker chooses a model from the vendored trend registry and an engine that the
registry measures for that model on this hardware, then launches it through the engine's
image. The one exception is Apple Silicon: Metal cannot be reached from a container, so the
engines whose skill declares a native `metal` install run on the host.

This document is the map of the shipped path and the machinery around it. It is refreshed by
`architecture-bot` (`make architecture-bot-brief` -> `make architecture-bot-doc` ->
`make architecture-bot-publish`) whenever the tree moves.

## The shipped path

1. **Bootstrap** — `make venv-install` builds the Python 3.11 gguf-tooling venv at
   `~/llama-gguf-tools/.venv` (deps from `tools/requirements.in` /
   `tools/requirements-dev.in`, compiled by `make -C tools generate-requirements`).
   `scripts/check_python.py`, run from `tools/Makefile`, keeps that venv on 3.11.
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
   `~/bin/llgenie.py` to this repo's `scripts/llgenie_serve.py`; `scripts/ensure_user_path.py`
   puts `~/bin` on the shell's path. `make test-built-engine` then runs every start script
   with `--version` through its image. `make ci-wait-engine-images` is the CI gate that
   waits for exactly those tags to appear in the registry before `install` runs (issue #169).
4. **Trend list** — `scripts/model_engine_pick.py` reads `data/models.json`, filters models
   to the ones whose VRAM tier fits this card, and ranks them. `recommend` is what plain
   `llgenie` shows: the upstream README "Most loved" order, with a stated reason on rows
   that cannot be served here; `rank_models` keeps that README order for models that have a
   runnable engine here, while each row's engines come from `rank_engines`, which orders
   them by a figure measured on this host's kind of hardware and card class first, so the
   engine list is what the registry measures for this machine, not a hand-kept list.
   `scripts/trend_list_matrix.py` renders the same list per `(arch, vram, ram)` into
   `tests/fixtures/trend-list-matrix.json`, which `make check-trend-list-matrix` guards and
   `llgenie --matrix` reproduces for one `(vram, ram, arch)`.
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
   runs natively through the skill's install because a container cannot reach the GPU there;
   picking a native engine installs it at the skill's pin through
   `scripts/install_engine_launchers.py` (`ensure_native`) and then starts it from `~/bin`.

## Launcher

`~/bin/llgenie` is the launcher the user runs: a small generated wrapper (`make link`) that
prepends `~/bin` to `PATH` and execs `~/llama-gguf-tools/.venv/bin/python` on
`scripts/llgenie_serve.py`; `~/bin/llgenie.py` is a symlink to that same script, so the
wrapper and the source cannot drift. One code path serves every engine — the launcher only
picks which start script or image to run.

- It scans `~/models/**/*.gguf` (`--list`) and, with no model named, walks hardware -> trend
  list -> model -> that model's engines -> engine (`--pick`, `--select N`, `--engine <id>`),
  showing which engines fit this machine and which are not installed yet.
- `--matrix` prints the model x engine x quant matrix for one `(vram, ram, arch)`
  (`--vram`, `--ram`, `--arch` override the detected host); `--download-top-tier
  [--family] [--count]` fetches trending models into the tiered
  `~/models/<family>/<size>` tree (e.g. `~/models/Qwen/8GB`); `--dry` prints the command
  instead of running it.
- It serves the OpenAI API on `127.0.0.1:${PORT:-11434}/v1` under the stable model id
  `llm-local`, and `--port` moves it.
- It resolves `llama-server` to the container shim and pulls an engine's image on first use
  (`scripts/install_engine_launchers.py --ensure <id>`), so an engine outside the default
  install plan needs no second `make install`.

## Repository layout

| Path | Role |
|---|---|
| `Makefile` | the only entry point for every stage and gate; CI calls `make <target>` and nothing else |
| `scripts/` | all logic: install, detection, pick, engine images/params, registry sync, bots, gates |
| `skills/engines/` | one `SKILL.md` per engine, the source `generate-engine-params` reads |
| `containers/engines/` | shared `base/` Dockerfiles, generated `dockerfiles/<id>/Dockerfile.<arch>`, frozen `params/`, `binaries.json`, `entrypoint.sh` |
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
| `.github/workflows/` | CI (`ci.yml`, `pipeline.yml`, `published.yml`, `publish-agent-image.yml`) and one workflow per bot |

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
keeps those PRs current. `scripts/engine_bump_sync.py` is the shared PR-sync logic and
`scripts/engine_params_derive.py` derives build parameters from the upstream tree without a
model in the loop.

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
  `make check-engine-skill-gap`; `make engine-skill-gap`, `make engine-skill-gap-md`,
  `make spawn-engine-skill-issues` report and file work from it).
- `data/trending-README.md` is the vendored upstream README the "Most loved" order comes
  from.
- `tests/fixtures/trend-list-matrix.json` is the rendered trend matrix
  (`make render-trend-list-matrix`, checked by `make check-trend-list-matrix`).

## CI

`.github/workflows/ci.yml` is the entry: `guard`, `ci-images` (publish the test and OpenSpec
images on a new hash, never rebuild per job), `engine-base`, `engine-matrix`,
`engine-image` (one parallel job per engine x backend), `engine-published-test`, and
`linux` / `macos`, which call `pipeline.yml` — the reusable per-OS verification pipeline.
`pipeline.yml` runs one job per `make ci-<job>` target (`ci-lint`, `ci-unit`,
`ci-agents-read`, `ci-openspec`, `ci-cpu-health`, `ci-top-tier`, `ci-install`), the same
jobs and asserts on both OSes; only the runner label differs. `linux-published` calls
`published.yml`, which runs `make ci-engines BACKEND=<b>` for `cpu`, `cuda`, `rocm` and
`vulkan` against the images the `engine-image` jobs published.
`publish-agent-image.yml` publishes the Hermes agent image (guarded to owner/collaborators,
amd64 only) — not the default job token: `ci-images` deliberately omits the agent image
because a brand-new package is refused "Create organization package".

Merging is CI's action, not a job inside `ci.yml`.
`.github/workflows/auto-merge.yml` is a `workflow_run` workflow on `CI`: a fork
`pull_request` run receives no repository secrets, so a merge job inside `ci.yml` would hold
an empty token and report success while merging nothing (issue #493). Running in the base
repository with the base repository's secrets, it resolves the PR from the finished run
(`scripts/resolve_run_pr.py` via `make auto-merge-resolve` — a 404 body from a fork run is
"no answer", never a value) and calls `make auto-merge` (`scripts/auto_merge.py`): squash
merge only for a non-draft PR that is `OPEN`, `MERGEABLE`, `CLEAN`, whose head is still the
run's sha, carries no `do-not-merge` label, and comes from this repository or the owner's
fork. A review-blocked green PR is approved with the other allowed identity and then
merged (`APPROVE=1`); everything else is deferred with the reason posted on the PR, never a
red run. After the merge `scripts/verify_closure.py` (`make verify-closure`) proves the
body's `closes #n` actually closed. `make auto-merge-explain` prints the verdict and writes
nothing.

The structural gates are make targets, so the same command runs locally and in CI:
`make check-workflows` (GitHub expressions parse, trailing newlines, every workflow has a
`name:`), `make check-dispatch-forms` (a dispatchable workflow documents its inputs and
stages), `make check-wiring` (every script/test reachable from a target CI runs),
`make check-docs` (every `##` make target is in `README.md`, every `agent-wiki/` entry
names its issue and PR), `make check-pr-hygiene`, `make check-pr-authors`,
`make check-secret-output`, `make check-agent-model` (the agent image's model pin equals the
one `scripts/agent_model_pin.py` declares), `make secret-scan` /
`make secret-scan-self-test`, plus `make bash-check` (`scripts/check_bash.py`, the bash-5
parity check that resolves the Makefile's shell) and `scripts/check_python.py`, which
`tools/Makefile` runs to keep the gguf venv on Python 3.11. All of them run inside
`make ci-unit`.

## Bots

Every bot is a workflow with its own cron slot, its own `concurrency:` group, an
owner/collaborator guard before any secret is read, and a transcript redacted by
`scripts/scrub_log.py` before any of it prints. No bot merges: the bots move branches,
comment and open PRs, and `.github/workflows/auto-merge.yml` is what lands a green,
conflict-free one (a reviewer holds a PR with the `do-not-merge` label). A bot's run inputs
(`issue.md`, `triage.md`, `refine-in.md`, `refine.md`, `comment.md`, `pr-body.md`) are
git-ignored: they are scratch a run writes, never repo content.

| Workflow | Cron | What it does |
|---|---|---|
| `issue-bot.yml` | `23 6 * * *` | implements ONE labeled/ready issue per run as a reviewable PR; a manual dispatch with no issue number picks one itself, the implementation is measured from the changed tree (not the exit code), the PR body is built from the run's `pr-body.md`, and a close verdict queues the canonical issue it cites (`scripts/issue_implementer.py`, issue #521) |
| `fix-bot.yml` | `17 * * * *` | repairs a red PR branch — including one whose head is the repository's own fork — re-runs the gate, pushes only when green |
| `rebase-bot.yml` | `29 */6 * * *` | drains every eligible PR onto `main` in one run, bounded by `max_prs`; decides from a computed merge state, hands a conflict to the agent and checks the resolution structurally (a recipe's TAB, the wiring guard, lint) against the checkout it mounted, aborts a stopped rebase so the tree returns to `main`, and pushes `--force-with-lease` to the PR's own head remote |
| `issue-refiner.yml` | `43 * * * *` | reviews one issue and refines or closes it with cited evidence |
| `code-review-bot.yml` | `31 7 * * 1` | files issues for findings in the tree and the pipelines |
| `registry-sync.yml` | `19 5 * * 1` | byte-copies the upstream registry, regenerates the derived tables, opens a PR |
| `engine-bump.yml` | `53 6 * * 1` | pins every engine skill to its upstream release |
| `engine-bump-rebase.yml` | `41 5 * * *` | keeps the engine-bump PRs current |
| `queued-alarm.yml` | `7,37 * * * *` | reports jobs stuck in `queued` |
| `search-smoke.yml` | `11 7 * * *` | proves the masked web reach works |
| `architecture-bot.yml` | `47 */6 * * *` | rewrites `docs/ARCHITECTURE.md` and opens one linked issue + PR |
| `run-failure-reactor.yml` | — (dispatch / `workflow_run`) | routes a failed run to the fix-bot or one deduped issue |
| `auto-merge.yml` | — (`workflow_run` on `CI`) | squash-merges the PR a green run belongs to when it is conflict-free; approves first as the other allowed identity; defers loudly otherwise |

Bots run inside the pinned agent image (`containers/agent`), call the model pinned once in
`scripts/agent_model_pin.py` (alias `nous-deepseek`,
`deepseek/deepseek-v4.1-flash-1017`) and are covered by
`tests/test_bot_pipeline_isolation.py` (no shared cron slot, no shared concurrency group).
Every leg runs `scripts/require_env.py` before the image is built (a missing credential is
loud, never a skip) and forwards credentials through the Makefile's `AGENT_SHELL_KEYS` /
`$(AGENT_SHELL_FORWARD)` seam; `make hermes-smoke` proves the model can call a tool,
`make agent-shell-keys-check` proves every forwarded credential is visible in the agent's
own shell, and `scripts/scrub_log.py` (`make scrub-log`) is the only thing that prints an
agent transcript.

Coordination lives in the tree, not in the workflows: `scripts/bot_claims.py` says which bot
is already working a subject, `scripts/rebase_bot_sweep.py` and
`scripts/fix_bot_sweep.py` decide the one PR a sweep acts on, `scripts/issue_cleaner.py`
finds an open issue a merged PR already implemented, and `scripts/worktree_prune.py`
(`make worktree-prune`, `DRY=1` to preview) removes the worktree and local branch of a
branch whose PR is merged.

## Tests and gates

`make test-unit` discovers every `tests/test_*.py` through `scripts/unit_tests.py`; a file
is in the gate the moment it exists, and an exclusion is a dated entry in
`tests/fixtures/unit-suite.json`. `make test` runs the named `groups.fast` subset from the
same roster rather than a hand-kept list of files. The live gates are separate targets
(`test-install`, `test-health`, `test-engine`, `test-published-engine`,
`test-native-engine*`, `test-top-tier*`, `test-hub-live`, `test-strata-live`,
`test-engine-bump-live`) and are never skipped: a missing prerequisite fails loudly. On an
Apple-Silicon host `make test-health` is the real GPU/Metal proof — it launches
`~/bin/llgenie` against the host's Metal `llama-server`; on Linux it answers "hi" through
the llama.cpp engine image.

`make loop` (`scripts/loop_harness.py`) chains image -> download -> lint -> agents-read ->
unit -> install -> health -> top-tier -> top-tier-serve -> test -> openspec ->
openspec-tasks -> clean, failing closed on any stage. `make check-docs`,
`make check-pr-hygiene`, `make check-pr-authors`, `make check-workflows`,
`make check-dispatch-forms`, `make check-wiring`, `make check-secret-output` and
`make check-agent-model` are the repository's structural gates. The data gates
(`check-registry`, `check-registry-keys`, `check-quant-catalog`,
`check-trend-list-matrix`, `check-engine-skill-gap`, `check-strata-models`,
`check-engine-params`, `skills-validate`) run inside `make ci-unit` alongside the unit
suite.

## Adding a change

An issue is the root; the branch, the OpenSpec change (`openspec/changes/<name>/`), the
code and the PR all trace back to it. Work happens in its own git worktree cut from
`origin/main`. The OpenSpec change is written before the code, each task is ticked when
verified, the README and an `agent-wiki/` entry land in the same commit, and the PR targets
`asimov-agent/llgenie:main` and closes the issue. The agent drives the PR green and stops:
`.github/workflows/auto-merge.yml` squash-merges it once the run is green and the PR is
conflict-free. The agent never runs `gh pr merge` and never pushes to `main`; a reviewer
holds a PR with `do-not-merge`, and `make worktree-prune` removes the worktree and branch
after the merge.
