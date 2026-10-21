# llgenie architecture

llgenie is a local GGUF model launcher with a hardware-aware picker. It does not compile or
run an inference server on the host: it detects the host's backend, pulls the matching
CI-built engine image from GHCR, and writes small start scripts into `~/bin` that run those
images. The picker chooses a model from the vendored trend registry and an engine that the
registry measures for that model on this hardware, then launches it through the engine's
image.

This document is the map of the shipped path. It is refreshed by `architecture-bot`
(`make architecture-bot-brief` -> `architecture-bot-doc` -> `architecture-bot-publish`)
whenever the tree moves.

## The shipped path

1. **Bootstrap** — `make venv-install` builds the Python 3.11 gguf-tooling venv
   (`~/llama-gguf-tools/.venv`, deps from `tools/requirements*.in` via pip-compile).
2. **Backend detection** — `scripts/detect_server.py` and `scripts/engine_runner.py` resolve
   the host's backend (`metal`, `cuda`, `rocm`, `vulkan`, `cpu`) from the GPU tree
   (`LLGENIE_BACKEND` overrides it).
3. **Install** — `scripts/install_engine_launchers.py` builds the install plan: which engine
   images this backend needs, from `LLGENIE_REGISTRY` (default `ghcr.io/asimov-agent`). It
   pulls only, never builds (`BUILD=1` is the explicit exception), writes
   `~/bin/llgenie-engine-<id>` per engine, `~/bin/llama-server` and `~/bin/prism-server`
   shims, and the `~/bin/llgenie` + `~/bin/llgenie.py` launcher. Then
   `make test-built-engine` makes every start script print its engine version through its
   image.
4. **Pick** — `scripts/model_engine_pick.py` reads `data/models.json`, filters by the host's
   VRAM/RAM, ranks models by the registry order, and ranks each model's engines by measured
   t/s on this hardware (`rank_models`, `rank_engines`). The engine list is what the trend
   registry says llgenie can run, not a hand-kept list.
5. **Engine skill** — `skills/engines/<id>/SKILL.md` is the one engine description: install
   steps, `container:` blocks per backend (`apt`, `cmake`, base image), the `detect`
   command, and the `metal` native path. `scripts/engine_skills.py` loads and validates
   them, and `make engine-skill-gap` / `spawn-engine-skill-issues` report a registry engine
   with no skill.
6. **Serve** — `scripts/llgenie_serve.py` scans `~/models/**/*.gguf`, sizes the KV cache and
   `-ngl` for the card, and runs the engine image (Metal runs natively because a container
   cannot reach the GPU there). The launcher speaks the OpenAI API over llama.cpp's
   `llama-server`.

## Repository layout

| Path | Role |
|---|---|
| `Makefile` | the only entry point for every stage and gate; CI calls `make <target>` and nothing else |
| `scripts/` | all logic: install, detection, pick, engine images/params, registry sync, bots, gates |
| `skills/engines/` | the per-engine skill (`SKILL.md`) the params generator reads |
| `containers/` | shared engine base Dockerfiles and the generated per-engine `dockerfiles/<id>/Dockerfile.<arch>` |
| `containers/test/` | the test image every Python gate runs in (no inference server inside it) |
| `data/` | vendored registry (`models.json`), engine registry, quant catalog, strata models, trend README |
| `openspec/` | the change record: `changes/<name>/{proposal.md,specs/**,tasks.md}` |
| `agent-wiki/` | dated work record, one entry per change, referencing its issue and PR |
| `tests/` | hermetic unit tests plus the live end-to-end gates, discovered by `scripts/unit_tests.py` |
| `docker-compose-files/` | the OpenSpec/test image compose definitions |
| `tools/` | pip-compile inputs (`requirements.in`, `requirements-dev.in`) |

## Engine images

`skills/engines/*/SKILL.md` is the source; `make generate-engine-params` is the only step
that reads it, and it writes the frozen params plus one Dockerfile per engine x arch. CI
builds `make build-engine ENGINE=<id> ARCH=<arch>`, tests the image
(`make test-engine` / `make test-engine-image`) and `make push-engine` publishes it to
`ghcr.io/<owner>/llgenie/<name>`. `scripts/engine_image.py` owns the tags, the matrix and
the `DISABLED` set (an image that cannot finish in CI is disabled with its tracking issue,
never left as a red job). GPU images never contain a driver: the host driver is mounted
through the container runtime (CDI for CUDA, `/dev/kfd` + `/dev/dri` for ROCm/Vulkan).

A weekly `engine-bump` pins each skill to its upstream release, derives the dependency
delta (`scripts/engine_deps.py`) and regenerates the Dockerfiles; `engine-bump-rebase`
keeps those PRs current.

## Data

- `data/models.json` is a **verbatim** copy of trending-local-llms' registry, replaced
  wholesale by the weekly `registry-sync` PR. `scripts/registry_keys.py`
  (`make check-registry-keys`) fails a sync that loses a model, a key, a measurement, a t/s
  or an engagement counter.
- `data/trending-quant-catalog.json` and `data/strata_models.json` are generated
  (`make sync-quant-catalog`, `make sync-strata-models`) and checked by their `check-*`
  targets.
- `data/trend-list-matrix.json` is the rendered trend matrix (`make
  render-trend-list-matrix`).

## CI

`.github/workflows/pipeline.yml` is the one pipeline: one job per `make ci-<job>` target
(`ci-lint`, `ci-unit`, `ci-agents-read`, `ci-openspec`, `ci-cpu-health`, `ci-top-tier`,
`ci-install`), the same jobs on Linux and macOS. `published.yml` runs the engine stage
(`make ci-engines BACKEND=<b>`) against the images published by the `engine-image-*` jobs;
`publish-agent-image.yml` publishes the agent image the bots run in. Every workflow file
must parse for GitHub and carry a `name:` (`make check-workflows`), every dispatchable
workflow must document its inputs and stages (`make check-dispatch-forms`), and every
script must be reachable from a target CI runs (`make check-wiring`).

## Bots

Every bot is a workflow with its own cron slot, its own `concurrency:` group, an
owner/collaborator guard before any secret is read, and a transcript redacted by
`scripts/scrub_log.py`. None of them merges; a human approves the PR.

| Workflow | Cron | What it does |
|---|---|---|
| `issue-bot.yml` | `23 6 * * *` | implements ONE labeled/ready issue per run as a reviewable PR |
| `fix-bot.yml` | `17 * * * *` | repairs a red PR branch, re-runs the gate, pushes only when green |
| `rebase-bot.yml` | `29 */6 * * *` | rebases stuck PRs onto `main` |
| `issue-refiner.yml` | `43 * * * *` | reviews one issue and refines or closes it with evidence |
| `code-review-bot.yml` | `31 7 * * 1` | files issues for findings in the tree and the pipelines |
| `registry-sync.yml` | `19 5 * * 1` | byte-copies the upstream registry and opens a PR |
| `engine-bump.yml` | `53 6 * * 1` | pins every engine skill to its upstream release |
| `engine-bump-rebase.yml` | `41 5 * * *` | keeps the engine-bump PRs current |
| `queued-alarm.yml` | `7,37 * * * *` | reports jobs stuck in `queued` |
| `search-smoke.yml` | `11 7 * * *` | proves the masked web reach works |
| `architecture-bot.yml` | `47 */6 * * *` | rewrites `docs/ARCHITECTURE.md` and opens one linked issue + PR |

Bots run inside the pinned agent image (`containers/agent`), call the pinned model alias
`nous-deepseek`, and are covered by `tests/test_bot_pipeline_isolation.py` (no shared cron
slot, no shared concurrency group).

## Tests and gates

`make test-unit` discovers every `tests/test_*.py` through `scripts/unit_tests.py`; a file
is in the gate the moment it exists, and an exclusion is a dated entry in
`tests/fixtures/unit-suite.json`. The live gates are separate targets
(`test-install`, `test-health`, `test-engine`, `test-published-engine`,
`test-native-engine*`) and are never skipped: a missing prerequisite fails loudly. `make
loop` chains download -> lint -> unit -> install -> health -> test -> openspec-validate,
and `make lint`, `make check-docs`, `make check-pr-hygiene`, `make check-pr-authors`,
`make check-workflows`, `make check-dispatch-forms` and `make check-wiring` are the
repository's structural gates.

## Adding a change

An issue is the root; the branch, the OpenSpec change (`openspec/changes/<name>/`), the
code and the PR all trace back to it. The OpenSpec change is written before the code, each
task is ticked when verified, the README and an `agent-wiki/` entry land in the same
commit, and the PR targets `asimov-agent/llgenie:main` and closes the issue.
