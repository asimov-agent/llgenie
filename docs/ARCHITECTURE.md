# llgenie architecture

llgenie is a local GGUF model launcher with a hardware-aware picker. It does not compile or
run an inference server on the host: it detects the host's backend, pulls the matching
CI-built engine image from GHCR, and writes small start scripts into `~/bin` that run those
images. The picker chooses a model from the vendored trend registry and an engine that the
registry measures for that model on this hardware, then launches it through the engine's
image. The one exception is Apple Silicon: Metal cannot be reached from a container, so the
engines whose skill declares a native `metal` install run on the host.

This document is the map of the shipped path and the machinery around it. It is refreshed by
`architecture-bot` (`scripts/architecture_bot.py`, workflow
`.github/workflows/architecture-bot.yml` on `47 */6 * * *`) in three deterministic stages:
`make architecture-bot-brief` derives the brief from the real tree and the git drift since
this doc's last commit, `make architecture-bot-doc` rewrites this file with Hermes inside the
agent image (the doc is the only writable file, and the transcript is redacted), and
`make architecture-bot-publish` files ONE issue + ONE linked PR for the change (`DRY=1`
previews). Nothing is published without drift, and the bot never merges.

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
   `offer` is the interactive hardware -> trend list -> model -> engines -> engine walk.
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
   engines with no skill are tracked by `scripts/engine_skill_gap.py` through
   `make engine-skill-gap` / `make spawn-engine-skill-issues`
   (`data/engine-skill-gap.json`, `data/unsupported-engines.json`).
6. **Engine image** — `make build-engine ENGINE=<id> ARCH=<arch>` builds strictly from the
   generated params and Dockerfile with plain make; `make test-engine` (OpenAI API answers
   on a tiny model) or `make test-engine-image` (version only, for GPU-only images) tests it,
   and `make push-engine` publishes it to `ghcr.io/<owner>/llgenie/<name>` as
   `<pinned-hash>-<arch>` and `:<arch>`.
7. **Serve** — `scripts/llgenie_serve.py` scans `~/models/**/*.gguf`, sizes the KV cache and
   `-ngl` for the card, resolves `llama-server` to the container shim (Prism on cards of
   24 GB or less, like `detect_server`), and serves the OpenAI API as `llm-local`. Its Hub
   read (`_hf_get`) retries both failure shapes: a connect-phase `URLError` **and** a
   read-phase socket timeout, which arrives as the builtin `TimeoutError` and used to kill a
   download mid-body with no retry (issue #549), on the `HF_GET_MAX_ATTEMPTS` budget
   (default 8).
   Metal runs natively through the skill's install because a container cannot reach the GPU
   there; picking a native engine installs it at the skill's pin through
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
| `scripts/` | all logic: install, detection, pick, engine images/params, registry sync, bots, gates, plus the shell legs the bots run |
| `skills/engines/` | one `SKILL.md` per engine (and a `README.md`), the source `generate-engine-params` reads |
| `containers/engines/` | shared `base/` Dockerfiles, generated `dockerfiles/<id>/Dockerfile.<arch>`, frozen `params/`, `binaries.json`, `entrypoint.sh` |
| `containers/test/` | the test image every Python gate runs in (`Dockerfile` only; no inference server inside it) |
| `containers/agent/` | the pinned Hermes agent image (`Dockerfile`) every bot leg runs in |
| `containers/ci-variant/` | the CUDA-toolkit variant-build image (`make test-variant-image`) with its own `requirements.txt` / `requirements-dev.txt` |
| `data/` | vendored registry, quant catalog, strata model map, engine-skill gap, unsupported engines, trending README |
| `docs/` | this document |
| `openspec/` | the change record: `config.yaml`, its `Dockerfile`, and `changes/<name>/{proposal.md,specs/**,tasks.md}` (191 changes) |
| `agent-wiki/` | dated work record (156 entries), one per change, referencing its issue and PR |
| `tests/` | 112 `tests/test_*.py` files, fixtures, shared test helpers (`tests/top_tier_dry_run.py`) and the live end-to-end gates, discovered by `scripts/unit_tests.py` |
| `docker-compose-files/` | the compose definitions for the OpenSpec CLI (`openspec.yaml`) and the test image (`test.yaml`) |
| `tools/` | pip-compile inputs (`requirements.in`, `requirements-dev.in`) and the venv targets |
| `.github/workflows/` | CI (`ci.yml`, `pipeline.yml`, `published.yml`, `publish-agent-image.yml`, `auto-merge.yml`) and one workflow per bot |
| `.editorconfig`, `.gitleaks.toml`, `pytest.ini`, `.env.example` | editor line-ending rules, the secret scanner's config, pytest settings, and the documented shape of the credentials a bot leg expects (never a real value) |

## Scripts

`scripts/` is a package (`scripts/__init__.py`, so the hermetic tests import it). The modules
group by what they exist for:

| Group | Modules |
|---|---|
| Product path | `llgenie_serve.py` (launcher, model scan, serve), `model_engine_pick.py` (`recommend`, `rank_models`, `rank_engines`, `offer`), `trend_list_matrix.py`, `detect_server.py`, `install_engine_launchers.py` (install plan, start scripts, `ensure_native`), `engine_runner.py`, `engine_skills.py`, `engine_image.py`, `native_build_env.py`, `serve_variant.py`, `ensure_user_path.py`, `hf_auth.py`, `hf_download.py`, `download_test_model.py`, `strata_models.py`, `sync_registry.py`, `gen_trending_quant_catalog.py`, `registry_keys.py`, `engine_skill_gap.py`, `engine_params_derive.py`, `engine_deps.py`, `engine_bump.py`, `engine_bump_sync.py`, `engine_bump_rebase.py`, `engine_smoke.py`, `env_seam.py`, `loopback_server.py` |
| Structural gates | `check_bash.py`, `check_python.py`, `check_docs.py`, `check_wiring.py`, `check_workflows.py`, `check_dispatch_forms.py`, `check_pr_authors.py`, `check_pr_hygiene.py`, `check_secret_output.py`, `check_openspec_tasks.py`, `secret_scan.py`, `secret_scan_self_test.py`, `scan_agents_md.py`, `module_name_guard.py`, `lint_linefeeds.py`, `unit_tests.py` (the suite aggregator) |
| CI entrypoints | `ci_engines.py` (`make ci-engines`), `ci_health.py`, `ci_images.py` (test/OpenSpec/agent image refs), `loop_harness.py` (`make loop`) |
| Bots and automation | `agent_model_pin.py`, `agent_shell_keys_check.py`, `architecture_bot.py`, `auto_merge.py`, `bot_claims.py`, `code_review.py`, `fix_bot_report.py`, `fix_bot_sweep.py`, `hermes_smoke.py`, `issue_cleaner.py`, `issue_dedup.py`, `issue_implementer.py`, `issue_refiner.py`, `queued_run_alarm.py`, `rebase_bot_sweep.py`, `require_env.py`, `resolve_run_pr.py`, `run_failure_reactor.py`, `scrub_log.py`, `verify_closure.py`, `web_evidence.py`, `fetch_smoke.py`, `worktree_prune.py` |

Two more pieces of `scripts/` are not Python: `scripts/tools/llgenie_harness.py` (the
harness helper the loop uses) and the shell legs the bot workflows call —
`agent_jev_preflight.sh`, `bot_sync_main.sh`, `build_llama_server.sh`, `fix_loop.sh`,
`install_hermes_ci.sh`, `install_nerve_ci.sh`, `load_token_to_env.sh`, `rebase_bot.sh` — plus
`scripts/fix_bot_rules.md`, the fix-bot's instruction sheet.

`scripts/module_name_guard.py` is the renamed-module guard: the CLI is
`scripts/llgenie_serve.py`, and its old spelling is refused in every live text file, this
doc included (issues #251, #573).

## Engine images

`skills/engines/*/SKILL.md` is the source; `make generate-engine-params` is the only step
that reads it, and it writes the frozen params plus one Dockerfile per engine x arch. CI
builds `make build-engine ENGINE=<id> ARCH=<arch>`, tests the image
(`make test-engine` / `make test-engine-image`) and `make push-engine` publishes it. The CI
`engine-image` job drives that post-build test through ONE step for every image,
`make test-engine-stage ENGINE=<id> ARCH=<arch> TEST=serve|detect`, which dispatches to
`test-engine` (the OpenAI API answers) or `test-engine-image` (the binary prints its
version). A published image is pulled back with no build and no cache by
`make test-published-engine`, which checks the digest, the binary version and — for CPU
images and GPU images with a CPU fallback — serves the tiny model and answers "hi".

`scripts/engine_image.py` owns the tags, the CI matrix and the `DISABLED` set (an engine x
arch image that cannot finish in CI is disabled with its tracking issue, never left as a
red job). GPU images never contain a driver: the host driver is mounted through the
container runtime (CDI for CUDA, `/dev/kfd` + `/dev/dri` for ROCm/Vulkan). Sixteen engine
directories carry a skill, and thirteen of them produce a container image:
`containers/engines/params/` and `containers/engines/dockerfiles/` each hold one entry per
servable engine — `llama.cpp`, `llama.cpp-prism`, `llama.cpp-laurentzuijdwijk`,
`exllamav3-rocm`, `vllm`, `sglang`, `ollama`, `mlx`, `strata`, `litert`, `tensorrt-llm`,
`freetoken` and `tensorfold`. The remaining three skills have no image: `webllm` declares
`servable: false` (a browser runtime) and `dflash2` / `mlx-fast-bonsai2` declare
`servable: via`, driven through another engine.

A weekly `engine-bump` pins each skill to its upstream release, derives the dependency
delta (`scripts/engine_deps.py`) and regenerates the Dockerfiles; `engine-bump-rebase`
keeps those PRs current. `scripts/engine_bump_sync.py` is the shared PR-sync logic and
`scripts/engine_params_derive.py` derives build parameters from the upstream tree without a
model in the loop.

## Data

`data/` holds six files, each generated or vendored, each with a make gate; the rendered
trend matrix lives under `tests/fixtures/`:

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
`pipeline.yml` runs one job per `make ci-<job>` target — `lint` (`ci-lint`), `unit`
(`ci-unit`), `install` (`ci-install`), `agents-read` (`ci-agents-read`), `openspec`
(`ci-openspec`), `cpu-health` (`ci-cpu-health`) and `top-tier` (`ci-top-tier`) — the same
jobs and asserts on both OSes; only the runner label differs. `linux-published` calls
`published.yml`, whose `install-published` job runs `make ci-engines BACKEND=<b>` for `cpu`,
`cuda`, `rocm` and `vulkan` against the images the `engine-image` jobs published.
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
merged (`APPROVE=1`); the approval is followed by a bounded wait — `wait_for_merge_state()`
re-reads the PR up to six times, five seconds apart, until `mergeStateStatus` is `CLEAN` —
because GitHub computes that field asynchronously and a read taken the same instant as the
approval still says `BLOCKED` (issue #531). A PR whose mergeability GitHub has not computed
yet is likewise polled until it has an answer instead of being deferred on `UNKNOWN`
(issue #558). Everything else is deferred with the reason posted on the PR, never a red
run; a PR that never converges keeps the `--admin` fallback and a deferral that names the
last observed state.

A deferral is exit 0 by design, so nothing retries it and a blocker that clears without a
push would wait forever. The workflow's second job, `recheck`, is that retry: it runs after
every CI completion (`needs: [merge]`, `if: always()`) and on its own schedule, and calls
`make auto-merge-recheck` (`scripts/auto_merge.py recheck`, `MAX=5`), which re-evaluates
only the PRs whose deferral marker `<!-- auto-merge: deferred <sha> -->` names their
**current** head (issue #545). Its cron is `3,33 * * * *`: the sweep sat on `*/30` and
produced zero scheduled runs while every other cron in this tree fired, so it moved to odd
minutes — the same rule queued-alarm and the bots follow (issues #275, #560).
After the merge `scripts/verify_closure.py` (`make verify-closure`) proves the body's
`closes #n` actually closed. `make auto-merge-explain` prints the verdict and writes
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
written at the repo root — `issue.md`, `triage.md`, `refine-in.md`, `refine.md`,
`comment.md`, `pr-body.md` (plus the captured `hermes-run.log`) — are git-ignored, and
`tests/test_bot_scratch_ignored.py` holds that list to real `git`: they are scratch a run
writes, never repo content. The dedupe sweep's `dedup-in.md` / `dedup.md` are the same kind
of scratch from `scripts/issue_dedup.py`; that workflow pushes and commits nothing, so they
never reach a tree.

| Workflow | Cron | What it does |
|---|---|---|
| `issue-bot.yml` | `23 6 * * *` | implements ONE labeled/ready issue per run as a reviewable PR; a manual dispatch with no issue number picks one itself, the implementation is measured from the changed tree (not the exit code), the PR body is built from the run's `pr-body.md`, and a close verdict queues the canonical issue it cites (`scripts/issue_implementer.py`, issue #521). Only a CLOSE is a decision: `agent:refined` is a marker that a restatement exists, so a refined issue stays in the picker's queue instead of becoming invisible to the implementer (issue #522) |
| `issue-refiner.yml` | `43 * * * *` | reviews one issue and refines or closes it with cited evidence (`scripts/issue_refiner.py`) |
| `issue-dedupe.yml` | `51 */6 * * *` | four times a day: picks ONE pair of similar **unclaimed** open issues, older as canonical (`scripts/issue_dedup.py`), has the agent decide `DUPLICATE: #<older>` with `EVIDENCE:`, and retires the copy with that comment + `agent:duplicate` while queueing the canonical — never touches a claimed issue, never opens a PR (issue #553) |
| `fix-bot.yml` | `17 * * * *` | repairs a red PR branch — including one whose head is the repository's own fork — re-runs the gate, pushes only when green; its sweep (`scripts/fix_bot_sweep.py`) treats a PR with no checks at all as not-red rather than a crash (issue #496). A `workflow_run` on a failed `CI` `pull_request` run makes the `sweep` job resolve that run to its PR (`make auto-merge-resolve`) and capture the failed job's log, then dispatch the repair — so a red PR is acted on in minutes rather than at the next hourly sweep (issue #538); `rounds` defaults to 5 and the job allows 260 minutes (issue #539) |
| `rebase-bot.yml` | `29 */6 * * *` | drains every eligible PR onto `main` in one run, bounded by `max_prs`; decides from a computed merge state, hands a conflict to the agent and checks the resolution structurally (a recipe's TAB, the wiring guard, lint) against the checkout it mounted, aborts a stopped rebase so the tree returns to `main`, and pushes `--force-with-lease` to the PR's own head remote |
| `code-review-bot.yml` | `31 7 * * 1` | files issues for findings in the tree and the pipelines (`scripts/code_review.py`) |
| `registry-sync.yml` | `19 5 * * 1` | byte-copies the upstream registry, regenerates the derived tables, opens a PR |
| `engine-bump.yml` | `53 6 * * 1` | pins every engine skill to its upstream release |
| `engine-bump-rebase.yml` | `41 5 * * *` | keeps the engine-bump PRs current |
| `queued-alarm.yml` | `7,37 * * * *` | reports jobs stuck in `queued` (`scripts/queued_run_alarm.py`) |
| `search-smoke.yml` | `11 7 * * *` | proves the masked web reach works (`scripts/fetch_smoke.py`) |
| `architecture-bot.yml` | `47 */6 * * *` | rewrites `docs/ARCHITECTURE.md` and opens one linked issue + PR (`scripts/architecture_bot.py`) |
| `run-failure-reactor.yml` | — (`workflow_run`) | reacts to a failed run of any workflow it lists and routes it: a PR it can push (this repository, or the owner's fork) becomes a fix-bot dispatch, made with the owner PAT because that bot's guard refuses a bot actor (issues #555, #556); anything else becomes ONE marker-deduped issue labelled `agent:implement` (`scripts/run_failure_reactor.py`, issue #286) |
| `auto-merge.yml` | `3,33 * * * *` + `workflow_run` on `CI` | squash-merges the PR a green run belongs to when it is conflict-free; approves first as the other allowed identity, waits for that approval and for GitHub's mergeability to settle, and its `recheck` job retries a deferral without a push at the head it still has |

Bots run inside the pinned agent image (`containers/agent`), call the model pinned once in
`scripts/agent_model_pin.py` (alias `nous-deepseek`,
`deepseek/deepseek-v4.1-flash-1017`) and are covered by
`tests/test_bot_pipeline_isolation.py` (no shared cron slot, no shared concurrency group).
Every leg runs `scripts/require_env.py` before the image is built (a missing credential is
loud, never a skip) and forwards credentials through the Makefile's `AGENT_SHELL_KEYS` /
`$(AGENT_SHELL_FORWARD)` seam; `make hermes-smoke` proves the model can call a tool,
`make agent-shell-keys-check` proves every forwarded credential is visible in the agent's
own shell (through `scripts/agent_shell_keys_check.py`), and `scripts/scrub_log.py`
(`make scrub-log`) is the only thing that prints an agent transcript. The one web reach is
`make agent-fetch` (Firecrawl key, text to `OUT`), with `make search-smoke` as its loud
proof and `make web-coverage` / `make issue-evidence` reading it from the tree.

Coordination lives in the tree, not in the workflows: `scripts/bot_claims.py` says which bot
is already working a subject, `scripts/rebase_bot_sweep.py` and
`scripts/fix_bot_sweep.py` decide the one PR a sweep acts on, `scripts/issue_cleaner.py`
finds an open issue a merged PR already implemented, `scripts/issue_dedup.py` decides which
pair of issues the dedupe sweep compares, and `scripts/worktree_prune.py`
(`make worktree-prune`, `DRY=1` to preview) removes the worktree and local branch of a
branch whose PR is merged.

## Tests and gates

`make test-unit` discovers every `tests/test_*.py` through `scripts/unit_tests.py` (112
files today); a file is in the gate the moment it exists, and an exclusion is a dated entry
in `tests/fixtures/unit-suite.json`. `make test` runs the named `groups.fast` subset from
the same roster rather than a hand-kept list of files. The live gates are separate targets
(`test-install`, `test-health`, `test-engine`, `test-published-engine`,
`test-native-engine*`, `test-top-tier*`, `test-hub-live`, `test-strata-live`,
`test-engine-bump-live`) and are never skipped: a missing prerequisite fails loudly. On an
Apple-Silicon host `make test-health` is the real GPU/Metal proof — it launches
`~/bin/llgenie` against the host's Metal `llama-server`; on Linux it answers "hi" through
the llama.cpp engine image.

The top-tier dry-run cases are the one place a live Hub read sits on a PR-blocking path.
`make ci-top-tier` runs `test-top-tier-ci`, `test-top-tier-serve-ci` and
`test-top-tier-cli-ci` in the `top-tier` job of `pipeline.yml`; the two `--dry` cases in
`tests/test_top_tier_acceptance.py` shell out through `tests/top_tier_dry_run.py`'s
`run_dry_run()`, which retries the whole dry run `TOP_TIER_DRY_RUN_ATTEMPTS` (2: the run
plus one retry) and only when the child's stderr names a Hub transport failure
(`[ERROR] HF API still failing after N attempts`, `TimeoutError`, `URLError`, connection
resets/errors, `SSLError`, resolution failures, or 429/502/503/504). Any other non-zero
exit is returned on the first attempt, so a bad argument or a real regression is never
retried into a green; a Hub that stays unreachable spends the bound and still exits
non-zero with the CLI's named cause (issue #399, locked by
`tests/test_top_tier_dry_run_retry.py`).

`make loop` (`scripts/loop_harness.py`) chains image -> download -> lint -> agents-read ->
unit -> install (`test-install-host`) -> health -> top-tier -> top-tier-serve -> test ->
openspec -> openspec-tasks -> clean, failing closed on any stage. `make check-docs`,
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
