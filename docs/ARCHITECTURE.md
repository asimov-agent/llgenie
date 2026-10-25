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
   generated params and Dockerfile with plain make. Whether a cell compiles or pulls is the
   params' decision: `prebuilt: false` compiles from the pinned sha on the shared
   `llgenie/base-<backend>` toolchain image (llama.cpp is a source build in all four
   variants), `prebuilt: true` starts `FROM` an upstream image and adds only the llgenie
   entrypoint. `make build-engines` builds every engine x variant the parameters declare,
   in parallel (`ENGINE=`, `ARCH=`, `JOBS=` and `FORCE=` narrow it); `make
   engine-build-matrix` is the same `scripts/engine_image.py matrix` JSON. `make test-engine`
   (OpenAI API answers on a tiny model) or `make test-engine-image` (binary flags and
   version only, for GPU-only images) tests a built image, `make engine-gate-report` prints
   what each cell will actually prove before anything is built, and `make push-engine`
   publishes a verified image to `ghcr.io/<owner>/llgenie/<name>` under three tags.
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
| `containers/agent/` | the pinned Hermes agent image (`Dockerfile`) every bot leg runs in: the Hermes CLI, the `nous-deepseek` model alias, the nerve plugin (installed, enabled and layered by `scripts/install_nerve_ci.sh` under the host's `operator` profile), the profile/settings parity check the build runs (`scripts/nerve_profile_check.py`), the `.hermes/skills` registration and the `agent_jev_preflight.sh` entry gate |
| `.hermes/skills/` | the bots' Hermes **project skills** — `issue-triage`, `issue-implement`, `issue-refiner`, `issue-dedup`, `pr-fix`, `rebase-conflict`, `architecture-doc`, `engine-params-review`, `agent-fetch`, `bot-unattended` (plus a `README.md`) — each leg's contract, preloaded with `hermes -s <name>` and guarded by `make check-agent-skills` (issue #577) |
| `containers/ci-variant/` | the CUDA-toolkit variant-build image (`make test-variant-image`) with its own `requirements.txt` / `requirements-dev.txt` |
| `data/` | vendored registry, quant catalog, strata model map, engine-skill gap, unsupported engines, trending README |
| `docs/` | this document |
| `openspec/` | the change record: `config.yaml`, its `Dockerfile`, and `changes/<name>/{proposal.md,specs/**,tasks.md}` (206 changes) |
| `agent-wiki/` | dated work record (172 entries), one per change, referencing its issue and PR |
| `tests/` | 123 `tests/test_*.py` files, fixtures, shared test helpers (`tests/top_tier_dry_run.py`) and the live end-to-end gates, discovered by `scripts/unit_tests.py` |
| `docker-compose-files/` | the compose definitions for the OpenSpec CLI (`openspec.yaml`) and the test image (`test.yaml`) |
| `tools/` | pip-compile inputs (`requirements.in`, `requirements-dev.in`) and the venv targets |
| `.github/workflows/` | CI (`ci.yml`, `pipeline.yml`, `published.yml`, `publish-agent-image.yml`, `auto-merge.yml`), the on-demand engine sweep (`engine-build.yml`) and one workflow per bot |
| `.editorconfig`, `.gitleaks.toml`, `pytest.ini`, `.env.example` | editor line-ending rules, the secret scanner's config, pytest settings, and the documented shape of the credentials a bot leg expects (never a real value) |

## Scripts

`scripts/` is a package (`scripts/__init__.py`, so the hermetic tests import it). The modules
group by what they exist for:

| Group | Modules |
|---|---|
| Product path | `llgenie_serve.py` (launcher, model scan, serve), `model_engine_pick.py` (`recommend`, `rank_models`, `rank_engines`, `offer`), `trend_list_matrix.py`, `detect_server.py`, `install_engine_launchers.py` (install plan, start scripts, `ensure_native`), `engine_runner.py`, `engine_skills.py`, `engine_image.py`, `native_build_env.py`, `serve_variant.py`, `ensure_user_path.py`, `hf_auth.py`, `hf_download.py`, `download_test_model.py`, `strata_models.py`, `sync_registry.py`, `gen_trending_quant_catalog.py`, `registry_keys.py`, `engine_skill_gap.py`, `engine_params_derive.py`, `engine_params_review.py` (the documentation review of a bump's derived params: `brief`, `parse_proposals`, `validate`, `apply_accepted`, `section`), `engine_deps.py`, `engine_bump.py`, `engine_bump_sync.py`, `engine_bump_rebase.py`, `engine_smoke.py`, `env_seam.py`, `loopback_server.py` |
| Structural gates | `check_bash.py`, `check_python.py`, `check_docs.py`, `check_wiring.py`, `check_workflows.py`, `check_dispatch_forms.py`, `check_pr_authors.py`, `check_pr_hygiene.py`, `check_secret_output.py`, `check_openspec_tasks.py`, `check_agent_skills.py` (a bot leg preloads its project skill, the skill exists and carries `Inputs`/`Output`/`Rules`, the prompt stays a pointer, and a skill list that comes from a Makefile variable is expanded before it is read), `engine_source_guard.py` (a cell that says `prebuilt: false` must actually compile), `engine_gate_report.py` (the per-cell census behind `make engine-gate-report`: `flag-proven`, `device-exempt` with its `DEVICE_ONLY` reason, or `disabled`), `secret_scan.py`, `secret_scan_self_test.py`, `scan_agents_md.py`, `module_name_guard.py`, `lint_linefeeds.py`, `unit_tests.py` (the suite aggregator) |
| CI entrypoints | `ci_engines.py` (`make ci-engines`), `ci_health.py`, `ci_images.py` (test/OpenSpec/agent image refs), `loop_harness.py` (`make loop`) |
| Bots and automation | `agent_model_pin.py`, `agent_shell_keys_check.py`, `architecture_bot.py`, `auto_merge.py`, `bot_claims.py`, `code_review.py`, `fix_bot_report.py`, `fix_bot_sweep.py`, `hermes_skills_register.py` (writes the checkout's skill dir into Hermes's `skills.external_dirs` as a real YAML list, and reads it back), `hermes_smoke.py`, `issue_cleaner.py`, `issue_dedup.py`, `issue_implementer.py`, `issue_refiner.py`, `nerve_profile_check.py` (fails the agent build when a nerve setting targets a module the chosen profile does not register), `queued_run_alarm.py`, `rebase_bot_sweep.py`, `require_env.py`, `resolve_run_pr.py` (resolves the PR a finished run belongs to; `--allow-none` is the fix-bot's answer for a PR that already landed), `run_failure_reactor.py`, `scrub_log.py`, `verify_closure.py`, `web_evidence.py`, `fetch_smoke.py`, `worktree_prune.py` |

Two more pieces of `scripts/` are not Python: `scripts/tools/llgenie_harness.py` (the
harness helper the loop uses) and the shell legs the bot workflows call —
`agent_jev_preflight.sh` (proves the Nerve JEV layer is live for THIS run, the first step of
every bot job), `bot_sync_main.sh`, `build_llama_server.sh`, `fix_loop.sh`,
`install_hermes_ci.sh` (installs the Hermes CLI and pins the `nous-deepseek` alias),
`install_nerve_ci.sh` (installs, scopes, enables and wires the nerve plugin at image-build
time, then proves its settings against the profile it selected), `load_token_to_env.sh`,
`rebase_bot.sh` — plus `scripts/fix_bot_rules.md`, the
fix-bot's instruction sheet.

`scripts/module_name_guard.py` is the renamed-module guard: the CLI is
`scripts/llgenie_serve.py`, and its old spelling is refused in every live text file, this
doc included (issues #251, #573).

## Engine images

`skills/engines/*/SKILL.md` is the source; `make generate-engine-params` is the only step
that reads it, and it writes the frozen params plus one Dockerfile per engine x arch. CI
builds `make build-engine ENGINE=<id> ARCH=<arch>`, tests the image
(`make test-engine` / `make test-engine-image`) and `make push-engine` publishes it. The CI
`engine-image` job drives that post-build test through ONE step for every image,
`make test-engine-stage ENGINE=<id> ARCH=<arch> TEST=serve|detect`. `TEST=serve` is the cpu
row: it runs `make test-engine-image` (the binary's flags) **and then** the OpenAI API answer
(`make test-engine`), joined with `&&`, so a cpu image can no longer reach the serve test
without its binary having been probed. `TEST=detect` is the GPU row: the binary's flags and
version only. A published image is pulled back with no build and no cache by
`make test-published-engine`, which checks the digest, the binary version and — for CPU
images and GPU images with a CPU fallback — serves the tiny model and answers "hi". Its
binary-flag pytest runs in the test image through `$(call engine_test,…)`, with
`LLGENIE_PUBLISHED_PULLED`, `LLGENIE_TEST_ENGINE` and `LLGENIE_TEST_ARCH` passed into the
container; a bare `python3 -m pytest` on the runner's own interpreter is what made six
`test-published-*` jobs red with `No module named pytest` while every earlier step passed
(issue #621), and `tests/test_make_pytest_seam.py` now fails any recipe line that runs pytest
without a seam.

The binary proof is per flag, never per binary (issue #580). `make push-engine` gates the
publish on `scripts/engine_image.py`'s `BINARY_PROBE`: the probe resolves the engine file
inside the image, runs EVERY flag it was given one at a time, and prints one
`LG-FLAG <flag> <rc> <bytes>` verdict line plus a bounded output block per flag, exiting 0
whenever the file was found and 1 only when it was not. `parse_probe()` turns that stdout
into `{flag: {rc, bytes, output}}` and `decide()` is the pure rule: every flag the engine's
`binaries.json` manifest documents must answer on its own, each of the flags a user types
(`TYPED_FLAGS`: `--version`, `-h`, `--help`, `-V`) is executed and reported, the help family
(`-h`/`--help`) and the version family (`--version`/`-V`) must each be answered by one of
their spellings, an engine documenting no flags still needs one answer from the fallback
trio, and at least one probed flag must exit 0 on every cell. One working spelling no longer
vouches for a dead one, so a release that drops a whole family reds on its own bump PR
instead of at a user's terminal.

The device-only exemption is keyed by the CELL, not by the binary alone (issues #625, #632,
#634/#637). `DEVICE_ONLY` is a dict keyed `(engine, variant)`, each entry carrying the
measured reason (the `vllm` cuda/rocm CLIs, `tensorrt-llm` cuda, `mlx` cuda — all four raise
at import without a device), so a cell that is not listed cannot be exempted, a listed cell's
exemption applies to itself only, and `decide()` refuses a `policy="device"` call that
arrives without `engine`/`variant` instead of silently answering "not exempt".
`binary_file_works()` passes `spec["id"]` and `spec["variant"]` on every path, so an engine
row decides through the product function with its cell's identity — the sweep's mlx/cuda row
used to fail there while the same check passed inside `test_image`. `make engine-gate-report`
(`scripts/engine_gate_report.py`) is the census a reviewer reads before a sweep: for every
engine x variant in the committed params it prints `flag-proven`, `device-exempt` (with its
`DEVICE_ONLY` reason) or `disabled` (with its `DISABLED` issue) plus the `detect` line, so
green rows can no longer hide cells that proved nothing but a file's presence.

`scripts/engine_image.py` owns the tags, the CI matrix, `CPU_FALLBACK` and the `DISABLED`
set (an engine x arch image that cannot finish in CI is disabled with its tracking issue,
never left as a red job). GPU images never contain a driver: the host driver is mounted
through the container runtime (CDI for CUDA, `/dev/kfd` + `/dev/dri` for ROCm/Vulkan).
Sixteen engine directories carry a skill, and thirteen of them produce a container image:
`containers/engines/params/` and `containers/engines/dockerfiles/` each hold one entry per
servable engine — `llama.cpp`, `llama.cpp-prism`, `llama.cpp-laurentzuijdwijk`,
`exllamav3-rocm`, `vllm`, `sglang`, `ollama`, `mlx`, `strata`, `litert`, `tensorrt-llm`,
`freetoken` and `tensorfold`. The remaining three skills have no image: `webllm` declares
`servable: false` (a browser runtime) and `dflash2` / `mlx-fast-bonsai2` declare
`servable: via`, driven through another engine.

Publishing names every image three ways (`publish_refs()`): the immutable HASH tag
(`<sha8>-<hash>-<variant>`), the moving `:<variant>` tag, and `:latest` — claimed by exactly
one variant per engine (`engine_latest_variant()`: `cpu` when the engine has one, otherwise
its only/first variant) so parallel publishing rows cannot race that tag. `pull_published()`
checks the digest of all of them: a `:latest` that is not there yet is a printed NOTE rather
than a failure, because it only exists once a run has published that engine, while a
`:latest` that exists with a different digest still fails.

`FORCE=1` is a real rebuild, not a skipped cache check (issue #638). `_buildx(force=True)`
passes `--no-cache` and reads no registry cache (fresh layers are still written back),
`build()` carries the flag through and forces its shared base too, `make build-engines`
forwards it into every row, and the dispatched sweep's `force` input does the same for the
whole matrix. Before that the sweep could only ever validate the layer cache — every row
printed `available -> no rebuild` — so a base/toolchain change, a poisoned cache, or a GHCR
tag that had to come from a clean build had no way to be republished.

The committed params hold 31 engine x arch cells; `CI_VARIANTS` and `DISABLED` leave 27 of
them as CI rows today, which is also what `make engine-build-matrix` emits. Of the 31 cells,
22 say `prebuilt: false` and 9 say `prebuilt: true` (`ollama` x4, `vllm` x3, `sglang` cuda,
`tensorrt-llm` cuda). Of the 22 source cells, 17 run their own build and 5 are tracked
exceptions. "From source" is a checked claim, not a comment: `make check-engine-source`
(`scripts/engine_source_guard.py`, run by `make ci-unit`) reads the committed params and
fails when a cell says `prebuilt: false` but its install steps only download a wheel or a
release archive, when a source cell clones an unpinned reference, or when its Dockerfile is
built `FROM` an upstream image of that same engine. A cell that genuinely cannot build yet is
recorded in the script's `KNOWN_NOT_SOURCE` with its reason and issue (`freetoken` cuda,
`litert` cpu, `mlx` cpu/cuda install a wheel; `tensorfold` cuda downloads the upstream release
tarball) — the census reports it and the gate fails only on a new cell, and converting one
means deleting its entry. `make engine-source-report` prints the whole census and never
fails.

`make build-engines` is the local parallel sweep over those rows: every engine x variant, or
`ENGINE=` / `ARCH=` / both, `JOBS=` wide (default `nproc`), `FORCE=1` rebuilding every row
from scratch, `VERIFY=1` also running each built image's binary test. In CI the same rows are
built by `.github/workflows/engine-build.yml`, the independent whole-set sweep described
under **CI** — `ci.yml` keeps its changed-images gate, so an unbuildable engine bump still
cannot merge.

A weekly `engine-bump` pins each skill to its upstream release, derives the dependency
delta (`scripts/engine_deps.py`) and regenerates the Dockerfiles; `engine-bump-rebase`
keeps those PRs current. `scripts/engine_bump_sync.py` is the shared PR-sync logic and
`scripts/engine_params_derive.py` derives build parameters from the upstream tree without a
model in the loop.

The derive proves the params **build**; it cannot prove they are **right** for this engine
version and this arch, because the extractors are structural (CMake options, renames,
recipe `-D` flags, toolchain pins). That gap is closed by a documentation review leg that
runs between the bump and the PR (issue #583), in three steps where the host stays the
writer:

1. `make engine-params-review-brief ENGINE=<id>` (`scripts/engine_params_review.py brief`)
   clones the engine's repo blobless and writes `params-review-in.md`: the parameters this
   repo builds with, plus a **ranked, bounded selection** of that engine's documentation at
   the pinned sha (issue #597). The selection is not the tree. `bench/`, `benchmarks/`,
   `examples/`, `tests/`, `fixtures/`, `assets/` and `apps/` never enter — the noise rule wins
   over the always-include rule, so a Dockerfile under `bench/results/…` is a bench artefact,
   not build evidence. The flag-proving files (`CMakeLists.txt`, `Dockerfile*`,
   `docker/**/Dockerfile*`) go first, root before nested, each cut at `ALWAYS_BUDGET` (60 KB)
   and all together at `ALWAYS_TOTAL_BUDGET` (45 KB) so they cannot starve the prose that
   explains the arch. Everything else (`README*`, `docs/*.md` / `docs/**/*.md`,
   `.github/**/*.md`, and the same rst forms) is scored on the vocabulary of building an
   engine (`option(`, `-D`, `CMAKE_`, `CUDA_ARCHITECTURES`, `GPU_TARGETS`, `cmake`, `cuda`,
   `rocm`, `hip`, `torch`, `pip install`, `apt-get`, `build`, `install`, `compile`) and taken
   highest first until `DOC_TOTAL_BUDGET` (80 KB) is spent. `docs/*.md` is listed explicitly
   in `DOC_GLOBS` because `Path.match` does not let `**` cross zero directories, which once
   hid `docs/BUILDING.md` — the page that documents the flags. The brief says what it did
   (`N file(s) selected by build relevance; M omitted for the 80 KB budget. This is a
   SELECTION of the tree, not all of it.`). The bounds are per file *and* in total because
   the per-file cap alone handed the leg 1.8 MB / 424 sections of mostly benchmark logs on
   `strata` v0.2.4 while the root `CMakeLists.txt` was cut below its `option(...)` lines;
   measured after, the same brief is 81 KB / 8 sections carrying the root `Dockerfile`, two
   `CMakeLists.txt`, three Dockerfiles and `docs/AMD_HIP.md` + `docs/DETAILS.md`.
2. `make engine-params-review ENGINE=<id>` is the agent leg — the `engine-params-review`
   Hermes project skill beside `bot-unattended`, run inside the agent image through
   `$(call scrubbed_run,…)` — and it writes the one file it may write, `params-review.md`,
   as `PROPOSE <backend> <flag> DOC <path> "<quote>" WHY <reason>` lines or a single
   `NO REVIEW: <reason>`.
3. `make engine-params-review-apply ENGINE=<id>` (`apply`, `DRY=1` previews and mutates
   nothing) validates: a proposal is accepted only when the backend is one the engine
   builds (or `common`), the named file exists at the pin, the flag's `NAME` appears in it,
   the quote is a substring of it (whitespace-normalised), and the flag is not already
   present. Accepted flags are appended to that backend's `cmake_flags.<backend>` line in
   the skill, `make generate-engine-params ENGINE=<id>` regenerates the params and
   Dockerfiles from it, and `params-review-section.md` records what was applied (with its
   document and quote) and every refusal with its reason.

In `.github/workflows/engine-bump.yml` that review step runs after the bump and before the
PR, is `continue-on-error`, and treats a failed brief, a failed review and a failed apply
each as a warning (`exit 0`): the bump still opens its PR, and the workflow appends
`params-review-section.md` to the PR body so the reviewer reads the doc quote rather than
re-deriving the build by hand. An uncited flag is dropped and reported, never applied — the
agent cannot invent a parameter.

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
images on a new hash, never rebuild per job), `engine-base`, `engine-matrix` (the committed
params, filtered by `CHANGED=<base>` to the images a PR touched), `engine-image` (one
parallel job per engine x backend), `engine-published-test` (pull each published image back
and run `make test-published-engine` on it), and `linux` / `macos`, which call
`pipeline.yml` — the reusable per-OS verification pipeline. `pipeline.yml` runs one job per
`make ci-<job>` target — `lint` (`ci-lint`), `unit` (`ci-unit`), `install` (`ci-install`),
`agents-read` (`ci-agents-read`), `openspec` (`ci-openspec`), `cpu-health` (`ci-cpu-health`)
and `top-tier` (`ci-top-tier`) — the same jobs and asserts on both OSes; only the runner
label differs. `linux-published` calls `published.yml`, whose `install-published` job runs
`make ci-engines BACKEND=<b>` for `cpu`, `cuda`, `rocm` and `vulkan` against the images the
`engine-image` jobs published.

`.github/workflows/engine-build.yml` is the independent whole-set sweep, and it is
deliberately not part of `ci.yml`: `ci.yml` builds only what a PR changed, which is the right
merge gate but means no run ever exercises the whole pinned set. The sweep is
`workflow_dispatch` only (inputs `engine`, `arch`, `push`, `force`; nothing schedules it),
never triggers on a pull request or a push, and never merges. `guard` runs first (owner or
collaborator with write, before any secret is read), then `matrix` runs
`make -s engine-build-matrix ENGINE=… ARCH=…` so the rows are the committed params and never
a hand-written roster, then one `build` job per row (`max-parallel: 20`) runs
`make build-engine`, `make test-engine-stage … TEST=<row.test>` in the row's own mode, and
only when `push=true` `make push-engine` as its own gated step — build, verify, publish, in
that order, so an image whose binary does not answer never reaches GHCR. `force=true` is
passed to the build step only (`FORCE=1`), so a dispatch can rebuild the whole matrix from
source instead of re-validating the layer cache; `force=true` with `push=true` is how every
tag is republished from a clean build — the hash tag, the moving `:<arch>` tag, and
`:latest` for each engine's canonical variant. Its `concurrency:` group is keyed by the
selection for a build-and-verify run and shared by every publishing run, so a narrow dispatch
runs alongside a full sweep instead of sitting behind it with zero jobs (issue #621), while
two pushes cannot race on the same `:<arch>` tag; `cancel-in-progress` is false, so a sweep
is never killed by a dispatch. The same scopes are available locally and in parallel from
`make build-engines`.

`publish-agent-image.yml` publishes the Hermes agent image (guarded to owner/collaborators,
amd64 only) — not the default job token: `ci-images` deliberately omits the agent image
because a brand-new package is refused "Create organization package". That image is built from
`containers/agent/Dockerfile`, which installs the Hermes CLI and the `nous-deepseek` alias
(`scripts/install_hermes_ci.sh`), registers `.hermes/skills`
(`scripts/hermes_skills_register.py`), installs and wires the nerve plugin
(`scripts/install_nerve_ci.sh`) on the `operator` profile, and then asserts each of them
back before the layer is committed — including, as the nerve step's last act,
`scripts/nerve_profile_check.py` against the installed plugin's own profile table, so a
setting whose module the profile does not register fails the image instead of shipping
inert (issue #611). `scripts/nerve_profile_check.py` is a hash input of that image, so a
change to the rule moves the tag.

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
`make check-secret-output`, `make check-engine-source` (a `prebuilt: false` cell must run a
real build, with its tracked exceptions reported — `make engine-source-report` prints the
census), `make check-agent-model` (the agent image's model pin equals the
one `scripts/agent_model_pin.py` declares), `make check-agent-skills` (every bot leg
preloads `.hermes/skills/<name>`, the skill exists with `Inputs`/`Output`/`Rules`, and the
inline prompt is a pointer — `make agent-skills-report` prints the legs and their skills),
`make secret-scan` /
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
`comment.md`, `pr-body.md`, the engine-bump review's `params-review-in.md` /
`params-review.md` / `params-review-section.md` (plus the captured `hermes-run.log`) — are
git-ignored, and `tests/test_bot_scratch_ignored.py` holds that list to real `git`: they are
scratch a run writes, never repo content. The dedupe sweep's `dedup-in.md` / `dedup.md` are
the same kind of scratch from `scripts/issue_dedup.py`; that workflow pushes and commits
nothing, so they never reach a tree.

| Workflow | Cron | What it does |
|---|---|---|
| `issue-bot.yml` | `23 6 * * *` | implements ONE labeled/ready issue per run as a reviewable PR; a manual dispatch with no issue number picks one itself, the implementation is measured from the changed tree (not the exit code), the PR body is built from the run's `pr-body.md`, and a close verdict queues the canonical issue it cites (`scripts/issue_implementer.py`, issue #521). Only a CLOSE is a decision: `agent:refined` is a marker that a restatement exists, so a refined issue stays in the picker's queue instead of becoming invisible to the implementer (issue #522) |
| `issue-refiner.yml` | `43 * * * *` | reviews one issue and refines or closes it with cited evidence (`scripts/issue_refiner.py`) |
| `issue-dedupe.yml` | `51 */6 * * *` | four times a day: picks ONE pair of similar **unclaimed** open issues, older as canonical (`scripts/issue_dedup.py`), has the agent decide `DUPLICATE: #<older>` with `EVIDENCE:`, and retires the copy with that comment + `agent:duplicate` while queueing the canonical — never touches a claimed issue, never opens a PR (issue #553) |
| `fix-bot.yml` | `17 * * * *` | repairs a red PR branch — including one whose head is the repository's own fork — re-runs the gate, pushes only when green; its sweep (`scripts/fix_bot_sweep.py`) treats a PR with no checks at all as not-red rather than a crash (issue #496). A `workflow_run` on a failed `CI` `pull_request` run resolves that run to its PR with `make fix-bot-resolve` (the same resolver as the merge gate, asked with `--allow-none`: an empty `number=` is an answer, so a failure reported after its PR already merged or closed ends the job cleanly instead of red and does not become a reactor issue — issue #629) and captures the failed job's log, then dispatches the repair — so a red PR is acted on in minutes rather than at the next hourly sweep (issue #538); `rounds` defaults to 5 and the job allows 260 minutes (issue #539) |
| `rebase-bot.yml` | `29 */6 * * *` | drains every eligible PR onto `main` in one run, bounded by `max_prs`; decides from a computed merge state, hands a conflict to the agent and checks the resolution structurally (a recipe's TAB, the wiring guard, lint) against the checkout it mounted, aborts a stopped rebase so the tree returns to `main`, and pushes `--force-with-lease` to the PR's own head remote |
| `code-review-bot.yml` | `31 7 * * 1` | files issues for findings in the tree and the pipelines (`scripts/code_review.py`) |
| `registry-sync.yml` | `19 5 * * 1` | byte-copies the upstream registry, regenerates the derived tables, opens a PR |
| `engine-bump.yml` | `53 6 * * 1` | pins every engine skill to its upstream release, then reviews the derived build params against that engine's own documentation at the new pin (`make engine-params-review-brief` -> `make engine-params-review` -> `make engine-params-review-apply`) and appends the review section to the PR body; the review is `continue-on-error`, so a failed or empty review still opens the PR and says so (issue #583) |
| `engine-bump-rebase.yml` | `41 5 * * *` | keeps the engine-bump PRs current |
| `queued-alarm.yml` | `7,37 * * * *` | reports jobs stuck in `queued` (`scripts/queued_run_alarm.py`) |
| `search-smoke.yml` | `11 7 * * *` | proves the masked web reach works (`scripts/fetch_smoke.py`) |
| `architecture-bot.yml` | `47 */6 * * *` | rewrites `docs/ARCHITECTURE.md` and opens one linked issue + PR (`scripts/architecture_bot.py`) |
| `run-failure-reactor.yml` | — (`workflow_run`) | reacts to a failed run of any workflow it lists and routes it: a PR it can push (this repository, or the owner's fork) becomes a fix-bot dispatch, made with the owner PAT because that bot's guard refuses a bot actor (issues #555, #556); anything else becomes ONE marker-deduped issue labelled `agent:implement` (`scripts/run_failure_reactor.py`, issue #286) |
| `auto-merge.yml` | `3,33 * * * *` + `workflow_run` on `CI` | squash-merges the PR a green run belongs to when it is conflict-free; approves first as the other allowed identity, waits for that approval and for GitHub's mergeability to settle, and its `recheck` job retries a deferral without a push at the head it still has |

The on-demand engine sweep (`.github/workflows/engine-build.yml`) sits outside this table: it
is a maintainer dispatch, not a bot, and it never merges, never runs on a schedule and never
publishes an image it has not verified.

Bots run inside the pinned agent image (`containers/agent`), call the model pinned once in
`scripts/agent_model_pin.py` (alias `nous-deepseek`,
`deepseek/deepseek-v4.1-flash-1017`) and are covered by
`tests/test_bot_pipeline_isolation.py` (no shared cron slot, no shared concurrency group).

Each leg's contract is a Hermes **project skill** (issue #577), not an inline rulebook:
`.hermes/skills/<name>/SKILL.md` — `issue-triage`, `issue-implement`, `issue-refiner`,
`issue-dedup`, `pr-fix`, `rebase-conflict`, `architecture-doc`, `engine-params-review`,
`agent-fetch` — preloaded with `hermes -s <name>,bot-unattended`, and the inline prompt is a
pointer plus the run's parameters (the input file, the output file). `bot-unattended`
carries the shared unattended contract once, and the deterministic step after the agent does
every GitHub write, so a leg writes only the one file its skill names.
`make check-agent-skills` (`scripts/check_agent_skills.py`, run by `make ci-unit`) fails a
leg with no `-s`, a name with no skill, a frontmatter `name` that disagrees with its
directory, a skill missing `Inputs` / `Output` / `Rules`, a prompt past the pointer budget,
or the unattended contract inlined again; `make agent-skills-report` prints the legs and the
skills, and `make test-agent-skills-live` proves the load through hermes-agent's own preload
path in the `agents-read-venv`. Hermes reads skills only from its own home and from
`skills.external_dirs`, so the image build registers the checkout's directory
(`make hermes-skills-register`, `scripts/hermes_skills_register.py`, called from
`scripts/install_hermes_ci.sh`): an unregistered checkout resolves `-s <name>` to nothing and
the leg runs with no contract while reporting success.

A leg's `-s` list may not carry a LITERAL comma, because a leg inlines its `hermes …`
command inside `$(call scrubbed_run,…)` and make splits the call's arguments on commas in the
unexpanded text (issue #641). `-s rebase-conflict,bot-unattended` therefore kept only
`-s rebase-conflict`, the shell saw an unclosed quote, and the rebase-bot leg exited 2 before
the agent started — every conflicted PR stayed `DIRTY` and reported "agent failed". The
skills now come from `REBASE_BOT_SKILLS` in the Makefile, `scripts/check_agent_skills.py`
expands Makefile variables before reading a leg's `-s` list (so it sees both skills rather
than the variable's name), and `tests/test_agent_legs_quoting.py` expands every scrubbed leg
with `make -n` and fails on an odd number of single quotes or a truncated skill list.

The agent image is also where the Nerve plugin is installed (#238, #585).
`scripts/install_nerve_ci.sh` runs at build time in three steps —
`hermes plugins install … --no-deps` (clone and record provenance without resolving), drop the
plugin's OPTIONAL `laya` extra from the installed `pyproject.toml` (asserted: a pin that stops
declaring it fails the build and names the decision), then `hermes plugins enable nerve`,
which resolves a graph that now has a solution. The one-shot `--yes-deps` form made Hermes
take a universal `uv lock` across every marker split, where `laya==0.3.3` → `torch>=2.0.0`
publishes no wheels for `python_full_version >= '3.14'` or `sys_platform == 'android'`, so
every image build failed; the extra is dead weight in this image because the bots run the
plugin's default `jev` backend and the plugin imports `laya` lazily. The script then writes
the host's flat `plugins.entries.nerve.settings.*` values (`gate_mode: advisory`,
`gate_scope: all`, `allow_tool_override false`, `context_engine_mode` /
`context_curation_mode: apply`, `nervous_enabled`), the `operator` profile sidecar through
the plugin's own `save_profile`, quotes `gate_mode` (YAML 1.1 reads a bare `off` as boolean
false, which turns the action gate ON), and proves through `hermes plugins list --json` that
the pinned commit is enabled and no provider token sits in the config. At run time
`make agent-jev-preflight` (`scripts/agent_jev_preflight.sh`) is the first step of every bot
job, with `NERVE_REQUIRE=1`: a leg whose JEV layer is off does not start, and its report is
redacted like every other agent stream.

The PROFILE and the SETTINGS are one decision, and the build now proves it (issue #611). For
a NAMED profile the module set comes verbatim from the plugin's `hermes_nerve/profiles.py`
(`modules = dict(PROFILES[name])`); the only later pass that reads settings can switch a
module OFF, never on. So a setting written for a module the profile does not register is
configured on paper and off in the run — which is what the image shipped: `lean` (no
`action_gate`, no `context_governor`) carrying `gate_mode: advisory`,
`context_engine_mode: apply` and `context_curation_mode: apply`, with nothing visibly
broken. The image is now built on the host's `operator` profile (reflex, nervous,
`action_gate`, `context_governor`, receipts, `local_learning`) with the gate in `advisory`,
`nerve_profile` written in the settings as well as the sidecar, and
`work_supervision_mode: shadow` because `operator` does not register that module.
`scripts/nerve_profile_check.py` encodes the rule once — `gate_mode != off` needs
`action_gate`, a `context_engine_mode` / `context_curation_mode` outside `shadow|off` needs
`context_governor`, `work_supervision_mode != shadow` needs `work_supervision`,
`nervous_enabled: true` needs `nervous` — and `scripts/install_nerve_ci.sh` runs it as its
last step against the INSTALLED plugin's own `PROFILES` table (not a copy of it), printing
the resolved module set and failing the image build when a setting and the profile disagree.
`make nerve-profile-check` runs the same rule's both-directions self-test on two synthetic
profile tables, so the rule is provable without a plugin install, and
`tests/test_agent_nerve.py` — in `make test-unit` — holds the image's profile, gate and
settings to the host's shape and checks that a `lean` table is rejected naming each inert
setting.

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
finds an open issue a merged PR already implemented, and `scripts/issue_dedup.py` decides
which pair of issues the dedupe sweep compares.

`scripts/worktree_prune.py` (`make worktree-prune`, `DRY=1` prints the plan and mutates
nothing) removes the worktree and local branch a merged PR left behind, and it decides from
the PR, never from ancestry — this repository squash-merges, so a branch tip is never an
ancestor of `main` and `git branch --merged` reports the work unmerged forever. A branch is
prunable only when it is the head of a MERGED PR whose merge commit is on the base.
Everything else is a KEEP with its reason printed: an open or closed PR, no PR at all, a
merge commit not on the base, the main checkout, the worktree the run is executing in, and a
dirty worktree. Two shapes needed the branch and the directory reconciled: a worktree git
reports as **detached** carries no branch name, so the plan indexes detached worktrees by
their HEAD commit and adopts exactly one parked on the prunable branch's tip (issue #570),
removing the directory before the branch; and a `git branch -D` refusal, the only authority
on which worktree holds a branch, is acted on rather than fatal (issue #593) — a worktree
that is detached, branch-less and clean is removed and the delete retried once (a second
refusal is still an error naming it), while a worktree with a branch checked out or holding
uncommitted/unmerged work turns the decision into a KEEP, so refusing to touch someone's
half-merged tree no longer exits 2 for the whole sweep. A refusal that names no worktree is
still a hard failure.

## Tests and gates

`make test-unit` discovers every `tests/test_*.py` through `scripts/unit_tests.py` (123
files today); a file is in the gate the moment it exists, and an exclusion is a dated entry
in `tests/fixtures/unit-suite.json`. `make test` runs the named `groups.fast` subset from
the same roster rather than a hand-kept list of files. The live gates are separate targets
(`test-install`, `test-health`, `test-engine`, `test-published-engine`,
`test-native-engine*`, `test-top-tier*`, `test-hub-live`, `test-strata-live`,
`test-engine-bump-live`) and are never skipped: a missing prerequisite fails loudly. On an
Apple-Silicon host `make test-health` is the real GPU/Metal proof — it launches
`~/bin/llgenie` against the host's Metal `llama-server`; on Linux it answers "hi" through
the llama.cpp engine image.

The engine seams are locked hermetically, without docker and without a model in the loop:
`tests/test_engine_params_review.py` (a documented per-arch flag is accepted and applied to
its own backend only, `DRY=1` mutates nothing, and an undocumented, uncited, wrong-backend
or already-present proposal is each refused with its reason, with the PR section reporting
both sides and the workflow step non-fatal and ordered before the PR; and the brief, on a
real git fixture dominated by bench pages and prose, keeps the root `CMakeLists.txt` past the
per-file cap inside the total budget, reports how many files it omitted, and ranks
`docs/BUILDING.md` ahead of prose — issue #597),
`tests/test_engine_binary_flags.py` (every flag is probed, one working spelling never
vouches for a dead one, and the families decide),
`tests/test_engine_gate_strict.py` (no flag answered is red, the device exemption is a named
list with a reason, and a version must look like a version — `0.0.0` and a log stamp are
not one),
`tests/test_engine_force_rebuild.py` (`FORCE=1` passes `--no-cache` and reads no registry
cache, the shared base is forced too, `build-engines` forwards it into every row, and a
publish carries the hash tag, `:<arch>` and a `:latest` claimed by one variant — with a
missing `:latest` a note and a drifted one a failure),
`tests/test_engine_build_workflow.py` (the sweep is dispatch-only, the guard runs first, the
matrix comes from `make engine-build-matrix` and the committed params rather than a roster,
every row is built and then verified, publishing is opt-in, and `force` reaches the build
step only),
`tests/test_engine_source_guard.py` (a `prebuilt: false` cell with no build is a finding, and
a tracked exception is reported rather than failing the gate),
`tests/test_agent_legs_quoting.py` (every scrubbed leg survives `make -n` with both quotes
balanced and its whole `-s` list intact), and
`tests/test_worktree_prune.py` (the detached-worktree match by HEAD, and a delete refusal
that splits into a one-shot retry or a keep).

`tests/test_make_pytest_seam.py` is the seam guard for the whole Makefile: it joins
`\`-continuations, ignores recipe comments, and fails any recipe line that runs
`python3 -m pytest` without `$(TEST_RUN)`, `$(ENGINE_TEST_RUN)`, `$(call engine_test,` or an
explicit `llgenie/test:latest` container — the runner's bare python has no pytest, so such a
line fails whatever it tests (issue #621). It also pins that `test-published-engine` passes
its env through `engine_test`.

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
`make check-dispatch-forms`, `make check-wiring`, `make check-secret-output`,
`make check-engine-source`, `make check-agent-model` and `make check-agent-skills` are the
repository's structural gates. The data gates
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
