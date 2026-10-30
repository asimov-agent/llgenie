# llgenie architecture

llgenie is a local GGUF model launcher with a hardware-aware picker. It does not compile or
run an inference server on the host: it detects the host's backend, pulls the matching
CI-built engine image from GHCR, and writes small start scripts into `~/bin` that run those
images. The picker chooses a model from the vendored trend registry and an engine that the
registry measures for that model on this hardware, then launches it through the engine's
image. The one exception is Apple Silicon: Metal cannot be reached from a container, so the
engines whose skill declares a native `metal` install run on the host.

This document is the map of the shipped path and the machinery around it. The user guide is
`README.md`; the per-engine build/serve detail is `docs/ENGINES.md`, the automation is
`docs/BOTS.md`, the scan pipeline is `docs/SCANS.md`, the scanner images are
`docs/SCANNERS.md`, the supply-chain pins are `docs/SECURITY.md`, dependency updates are
`docs/RENOVATE.md`, and every change's own record is a dated note in `agent-wiki/` indexed by
`CHANGES.md`. It is refreshed by `architecture-bot` (`scripts/architecture_bot.py`, workflow
`.github/workflows/architecture-bot.yml` on `47 */6 * * *`) in three deterministic stages:
`make architecture-bot-brief` derives the brief from the real tree and the git drift since
this doc's last commit, `make architecture-bot-doc` rewrites this file with Hermes inside the
agent image (the doc is the only writable file, and the transcript is redacted), and
`make architecture-bot-publish` files ONE issue + ONE linked PR for the change (`DRY=1`
previews). Nothing is published without drift, and the bot never merges.

## The shipped path

1. **Bootstrap** — `make venv-install` builds the Python 3.11 gguf-tooling venv at
   `~/llama-gguf-tools/.venv` (deps from `tools/requirements.in` /
   `tools/requirements-dev.in`, compiled by `make -C tools generate-requirements`). Both `.in`
   files include the generated constraint file `tools/security-floors.in` with
   `-c security-floors.in`, so the scanner's minimum versions reach the compiled pins without
   anyone editing them (issue #738). `scripts/check_python.py`, run from `tools/Makefile`,
   keeps that venv on 3.11.
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
   with `--version` through its image, and `make ci-wait-engine-images` is the CI gate that
   waits for exactly those tags to appear in the registry before `install` runs (issue #169).
   A single tree/backend can be installed on its own with `make install-prism-cpu`,
   `make install-upstream-cpu`, `make install-prism-cuda` or `make install-upstream-cuda`; on
   macOS the native forms are `make install-prism-metal` / `make install-upstream-metal`,
   built by `make build-variant TREE=prism|upstream BACKEND=metal`. `make uninstall` reverses
   all of it (launcher, start scripts, shims, engine containers; `PURGE_IMAGES=1` also drops
   the images) and `make test-uninstalled` proves nothing of ours is left behind.
4. **Trend list** — `scripts/model_engine_pick.py` reads `data/models.json`, filters models
   to the ones whose VRAM tier fits this card (`trend_list` also applies the store's own
   `system_ram_min` floor when it states one, so a host without the RAM is never shown a
   row), and ranks them. `recommend` is what plain `llgenie` shows: the upstream README
   "Most loved" order, with a stated reason on rows
   that cannot be served here; `rank_models` keeps that README order for models that have a
   runnable engine here, while each row's engines come from `rank_engines`, which orders
   them by a figure measured on this host's kind of hardware and card class first, so the
   engine list is what the registry measures for this machine, not a hand-kept list.
   A measurement is not a download: `engine_has_a_plan` drops an engine the committed HF
   class table (`data/trending-quant-catalog.json`) has no cell for, because the table is
   generated with the store and an engine without a plan fails at download time instead of
   at pick time (issue #750); a model the table does not cover yet keeps live resolution,
   so a freshly synced store is still served. `offer` is the interactive hardware -> trend
   list -> model -> engines -> engine walk.
   `scripts/trend_list_matrix.py` renders the same list per `(arch, vram, ram)` into
   `tests/fixtures/trend-list-matrix.json`, which `make check-trend-list-matrix` guards and
   `llgenie --matrix` reproduces for one `(vram, ram, arch)`; `trend_rows` asks `trend_list`
   for the RAM gate too, so it never renders a row `matrix()` did not consider.
5. **Engine skill** — `skills/engines/<id>/SKILL.md` is the one engine description: install
   steps, `container:` blocks per backend (`apt`, `cmake`, base image), the `detect`
   command, and the native `metal` path. `scripts/engine_skills.py` is the generic loader and
   runner (no engine-specific code); `make engine-list` lists the skills with their
   servable/backends/fit, `make engine-hardware` shows the detected parameters a skill renders
   against, `make engine-plan ENGINE=<id>` renders that engine's install and launch here,
   `make engine-check` reports what blocks installing it, `make engine-install` runs the
   skill, and `make engine-detect` asks whether it is already installed.
   `make generate-engine-params` is the only step that reads the skills: it freezes each one
   into `containers/engines/params/<id>.json` (one variant per backend x GPU arch) plus
   `containers/engines/binaries.json`, and writes one Dockerfile per engine x arch under
   `containers/engines/dockerfiles/<id>/` (`make generate-build-engine-params` is the alias).
   Registry engines with no skill are tracked by `scripts/engine_skill_gap.py` through
   `make engine-skill-gap` / `make spawn-engine-skill-issues`
   (`data/engine-skill-gap.json`, `data/unsupported-engines.json`), and
   `make check-engine-skill-gap` (in `make ci-unit`) keeps a registry that names a new
   engine red until it ships a skill or a dated decision (issue #683). The tracking issue
   the sync files is labelled `agent:implement` through the REST label endpoint
   (`POST repos/<repo>/issues/<n>/labels`) and read back, failing the step when the label is
   absent — neither the create's `--label` (dropped) nor `gh issue edit --add-label`
   (GraphQL, refused by the runner's PAT) is trusted (#724/#757). It names
   `make engine-skill-scaffold ENGINE="<registry name>"` — the target that writes the
   skill from the registry's own entry and leaves every unprovable key EMPTY, so
   `make skills-validate` names the remaining work rather than a guessed pin building. The one
   key it derives is `os:`, from the same backend evidence: `Metal` alone is `darwin` (native,
   never an image), Metal plus a Linux backend is both, no Metal is `linux` (issue #772).
6. **Engine image** — `make build-engine ENGINE=<id> ARCH=<arch>` builds strictly from the
   generated params and Dockerfile with plain make; the shared toolchain layer under it is
   `make build-engine-base BACKEND=<cpu|cuda|rocm|vulkan>` (`PUSH=1` publishes it).
   Whether a cell compiles or pulls is the params' decision: `prebuilt: false` compiles from
   the pinned sha on the shared `llgenie/base-<backend>` toolchain image (llama.cpp is a
   source build in all four variants), `prebuilt: true` starts `FROM` an upstream image and
   adds only the llgenie entrypoint. `make build-engines` builds every engine x variant the
   parameters declare, in parallel (`ENGINE=`, `ARCH=`, `JOBS=` and `FORCE=` narrow it);
   `make list-engine-images` prints the same cells (`CI=1` only the CI variants, `JSON=1` as
   a GitHub matrix, `CHANGED=<ref>` only those whose tag differs), and
   `make engine-build-matrix` is the matrix the dispatched sweep builds. `make test-engine`
   (OpenAI API answers on a tiny model) or `make test-engine-image` (binary flags and
   version only, for GPU-only images) tests a built image, `make run-engine` serves one on
   `127.0.0.1:$(PORT)/v1` and `make stop-engine` stops it, `make engine-gate-report` prints
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

The tree is 1992 tracked files: `data/` 9, `skills/` 17 (16 engine directories plus their
`README.md`), `containers/` 57, `tests/` 201, `scripts/` 120, `openspec/` 1031, `agent-wiki/`
243 and `docs/` 250. (measured at `15eb17c`)

| Path | Role |
|---|---|
| `Makefile` | the only entry point for every stage and gate; CI calls `make <target>` and nothing else |
| `scripts/` | all logic: install, detection, pick, engine images/params, registry sync, scans, bots, gates, plus the shell legs the bots run |
| `skills/engines/` | one `SKILL.md` per engine (and a `README.md`), the source `generate-engine-params` reads |
| `containers/engines/` | shared `base/` Dockerfiles, generated `dockerfiles/<id>/Dockerfile.<arch>`, frozen `params/`, `binaries.json`, `entrypoint.sh` |
| `containers/scanners/` | one Dockerfile per scanner (`trivy/`, `grype/`, `semgrep/`) plus the generated `digests.json` the scan workflow pins by digest (issues #714, #715) |
| `containers/test/` | the test image every Python gate runs in (`Dockerfile` only; no inference server inside it) |
| `containers/agent/` | the pinned Hermes agent image (`Dockerfile`) every bot leg runs in: the Hermes CLI, the `nous-deepseek` model alias, the nerve plugin (installed, enabled and layered by `scripts/install_nerve_ci.sh` under the host's `operator` profile), the profile/settings parity check the build runs (`scripts/nerve_profile_check.py`), the `.hermes/skills` registration and the `agent_jev_preflight.sh` entry gate |
| `.hermes/skills/` | the Hermes **project skills** — `issue-triage`, `issue-implement`, `issue-refiner`, `issue-dedup`, `pr-fix`, `rebase-conflict`, `architecture-doc`, `engine-params-review`, `registry-sync-review`, `agent-fetch`, `bot-unattended` (plus a `README.md`), each leg's contract preloaded with `hermes -s <name>`, and the HOST skill `llgenie-architecture-pass`, which no leg preloads (admitted by name in `HOST_SKILLS`) — all guarded by `make check-agent-skills` (issues #577, #805) |
| `containers/ci-variant/` | the CUDA-toolkit variant-build image (`make test-variant-image`): its `Dockerfile` only — the two lockfiles are copied from `tools/` into a temp build context and are never tracked here (a committed copy is a stale pin the scan can never clear, issue #787) |
| `data/` | vendored registry, the vendored model contract (schema + prose) it is validated against, quant catalog, strata model map, engine-skill gap, unsupported engines, trending README, and the scan failure/issue policy |
| `docs/` | `ARCHITECTURE.md` (this map), `ENGINES.md` (per-engine build/serve), `BOTS.md` (automation, crons, credentials), `SCANS.md` (the scan pipeline), `SCANNERS.md` (scanner images), `SECURITY.md` (supply-chain pins), `RENOVATE.md` (dependency updates), and `changes.d/` (one index row per change — the change index is a directory, never one shared table, issue #934) |
| `openspec/` | the change record: `config.yaml`, its `Dockerfile`, and `changes/<name>/{proposal.md,specs/**,tasks.md}` (264 changes) |
| `agent-wiki/` | dated work record (243 entries), one per change, referencing its issue and PR |
| `CHANGES.md` | those notes' index, newest first — one row rendered from each `docs/changes.d/<note>.md` by `make changes-index`; a note with no row, or a row naming a missing note, fails `make check-docs` (issues #678, #934) |
| `tests/` | 171 `tests/test_*.py` files, fixtures, shared test helpers (`tests/top_tier_dry_run.py` for the live Hub dry run, `tests/hub_probe.py` for a probe's verdict on one Hub file) and the live end-to-end gates, discovered by `scripts/unit_tests.py` |
| `docker-compose-files/` | the compose definitions for the OpenSpec CLI (`openspec.yaml`) and the test image (`test.yaml`) |
| `tools/` | pip-compile inputs (`requirements.in`, `requirements-dev.in`), the generated `security-floors.in` constraint file, and the venv targets |
| `renovate.json` | the dependency / base-image update config Renovate acts on; its properties are a gate (`make check-renovate`), not a preference |
| `.github/workflows/` | CI (`ci.yml`, `pipeline.yml`, `published.yml`, `publish-agent-image.yml`, `auto-merge.yml`), the on-demand engine sweep (`engine-build.yml`), the daily scan (`security-scan.yml`) and one workflow per bot |
| `.editorconfig`, `.gitleaks.toml`, `pytest.ini`, `.env.example` | editor line-ending rules, the secret scanner's config, pytest settings, and the documented shape of the credentials a bot leg expects (never a real value) |

## Scripts

`scripts/` is a package (`scripts/__init__.py`, so the hermetic tests import it). The modules
group by what they exist for:

| Group | Modules |
|---|---|
| Product path | `llgenie_serve.py` (launcher, model scan, serve), `model_engine_pick.py` (`recommend`, `rank_models`, `rank_engines`, `engine_has_a_plan` — the catalog cell an engine must have before it is offered — `offer`), `trend_list_matrix.py` (`trend_rows`), `detect_server.py`, `install_engine_launchers.py` (install plan, start scripts, `ensure_native`), `engine_runner.py`, `engine_skills.py`, `engine_image.py`, `native_build_env.py`, `serve_variant.py`, `ensure_user_path.py`, `hf_auth.py` (the ONE Hub request policy: token on Hub endpoints only, 429 waits the `RateLimit` window), `hf_download.py`, `download_test_model.py`, `strata_models.py`, `sync_registry.py` (vendor the store + its README + its contract, and `check` the store against that contract; the `FORMAT_VOCAB` the normaliser drops non-format names by), `gen_trending_quant_catalog.py` (`_repos_for` applies `plan_download()`'s own repo rule to every planned cell), `registry_keys.py` (additive-only guard; a format is compared by its vocabulary spelling), `engine_skill_gap.py`, `engine_params_derive.py`, `engine_params_review.py` (the documentation review of a bump's derived params: `brief`, `parse_proposals`, `validate`, `apply_accepted`, `section`), `engine_deps.py`, `engine_bump.py`, `engine_bump_sync.py`, `engine_bump_rebase.py`, `engine_smoke.py`, `env_seam.py`, `loopback_server.py` |
| Security pipeline | `security_scan.py` (`ref`, `sbom`, `scan`, `all`, `verdict`, `findings`, `check` — the ONE place a scanner is invoked, from the image `containers/scanners/digests.json` pins), `scanner_image.py` (`digest`, `ref`, `build`, `test`, `publish`, `write`, `check` for one immutable image per scanner), `security_issues.py` (findings -> tagged issues, keyed by `<!-- security-finding: <tool>:<advisory>:<package> -->`, updated in place), `security_bumps.py` (derive the floor per package, write `tools/security-floors.in`, regenerate the compiled pins, open ONE PR that closes the issues it fixes), `security_bot.py` (`select`, `plan`, `check` — one `auto-fixable` issue -> one green PR, or a comment when it cannot place the finding), `check_renovate.py`, `pin_actions.py` (`check`, `report`, `update`) |
| Structural gates | `check_bash.py`, `check_python.py`, `check_docs.py` (user-facing target documented, README stays a user guide, every `agent-wiki/` note names an issue/PR and is indexed in `CHANGES.md`), `check_architecture_census.py` (`make check-architecture-census` — parses this document's census, counts the tree with `git ls-tree -r --name-only HEAD`, and fails when they disagree, naming both values; wired into `check-docs`, issue #896), `check_wiring.py`, `check_workflows.py`, `check_dispatch_forms.py`, `check_pr_authors.py`, `check_pr_hygiene.py`, `check_issue_body.py` (the issue-body gate over `issue_body.PRODUCERS`), `check_secret_output.py`, `check_openspec_tasks.py`, `check_agent_skills.py` (a bot leg preloads its project skill, the skill exists and carries `Inputs`/`Output`/`Rules`, the prompt stays a pointer, and a skill list that comes from a Makefile variable is expanded before it is read), `issue_bot_gates.py` (the FAST gates the issue-bot re-runs before it pushes, plus the static lock on which `ci-unit` gates are fast and where the step sits), `engine_coverage.py` (every shipped engine's skill has an image some CI variant actually builds, with today's gap recorded in `KNOWN_UNBUILT`), `engine_source_guard.py` (a cell that says `prebuilt: false` must actually compile), `engine_gate_report.py` (the per-cell census behind `make engine-gate-report`: `flag-proven`, `device-exempt` with its `DEVICE_ONLY` reason, or `disabled`), `secret_scan.py`, `secret_scan_self_test.py`, `scan_agents_md.py`, `module_name_guard.py`, `lint_linefeeds.py` (trailing newline **and** a blank line before every markdown heading), `unit_tests.py` (the suite aggregator) |
| CI entrypoints | `ci_engines.py` (`make ci-engines`), `ci_health.py`, `ci_images.py` (test/OpenSpec/agent image refs), `engine_matrix_pushed.py` (did this run push an engine image? — the one fact `ci.yml` asks before it starts the four `install-published-*` rows, so a PR never re-proves the registry instead of the diff, issue #844), `loop_harness.py` (`make loop`) |
| Bots and automation | `agent_model_pin.py`, `agent_shell_keys_check.py`, `architecture_bot.py`, `auto_merge.py`, `bot_claims.py`, `code_review.py`, `engine_skill_scaffold.py` (writes the `skills/engines/<id>/SKILL.md` a registry engine needs, derived from the registry's own entry, so a spawned engine issue has a first barrel to implement against), `fix_bot_report.py`, `fix_bot_sweep.py`, `hermes_skills_register.py` (writes the checkout's skill dir into Hermes's `skills.external_dirs` as a real YAML list, and reads it back), `hermes_smoke.py`, `issue_body.py` (the ONE issue-body renderer, with `PRODUCERS` naming every producer of one), `issue_cleaner.py`, `issue_dedup.py`, `issue_implementer.py`, `issue_refiner.py` (a `DRY=1` pick prints the issue it chose and writes nothing into the checkout it previews, issue #352), `nerve_profile_check.py` (fails the agent build when a nerve setting targets a module the chosen profile does not register), `queued_run_alarm.py`, `rebase_bot_sweep.py`, `registry_change_issue.py` (states what a vendored store changed vs `HEAD` and files ONE issue keyed by its `generated_utc`), `registry_review.py` (the green-sync-PR review: `brief` renders the precondition plus the VRAM selection check from `trend_list()` / `rank_engines()`, `publish` files ONE `agent:implement` issue keyed by the same marker), `require_env.py`, `resolve_run_pr.py` (resolves the PR a finished run belongs to; `--allow-none` is the fix-bot's answer for a PR that already landed), `run_failure_reactor.py`, `scrub_log.py`, `verify_closure.py`, `web_evidence.py`, `fetch_smoke.py`, `worktree_prune.py` |

Two more pieces of `scripts/` are not Python: `scripts/tools/llgenie_harness.py` (the
harness helper the loop uses) and the shell legs the bot workflows call —
`agent_jev_preflight.sh` (proves the Nerve JEV layer is live for THIS run, the first step of
every bot job), `bot_sync_main.sh`, `build_llama_server.sh`, `fix_loop.sh`,
`install_hermes_ci.sh` (installs the Hermes CLI and pins the `nous-deepseek` alias),
`install_nerve_ci.sh` (installs, scopes, enables and wires the nerve plugin at image-build
time, then proves its settings against the profile it selected), `load_token_to_env.sh`,
`rebase_bot.sh`.

`scripts/module_name_guard.py` is the renamed-module guard: the CLI is
`scripts/llgenie_serve.py`, and its old spelling is refused in every LIVE file, this doc
included (issues #251, #573). "Live" is the tree walk minus the checkout's own `.gitignore`
rules (`live_files()` / `is_ignored()`), because a guard that read everything judged files git
never tracks — a bot's git-ignored working file reddened the local `make loop` while CI, on a
fresh checkout, stayed green (issue #350). The matcher is deliberately minimal (a `dir/`
prefix, a `*.ext` name, a literal path) and works where `git ls-files` does not, since the unit
suite runs in the test image with `.git` pointing outside the mount.

`make check-module-names` is the target `ci-unit` runs, and it is the CLI, not the library
(issue #812). The CLI excludes exactly one file — the guard's own test, which spells the
forbidden name because that is what it asserts — through the module-level `SELF_EXCLUDED`
constant, so the exclusion is a dated decision with a reason rather than a hole: `--include-self`
judges it too and refuses it, and a planted old-name file in any other live path fails the
target. Before #812 the constant did not exist, `main()` never passed the library's `exclude`
seam, and no target ran the guard at all — so the rule was asserted in this paragraph and
enforced nowhere.

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

`make engine-smoke` is the host entry point that installs one engine through its skill and
serves a tiny model; CI's per-engine serve check is `make test-engine-stage TEST=serve` in
the `engine-image` jobs, plus `make test-published-engine` on the published image.

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
instead of at a user's terminal. A version must also look like a version: `0.0.0` (the
placeholder a wheel with missing packaging metadata reports) and a log stamp are refused, and
the fallback an engine's `detect` uses is the pinned VERSION, never the commit sha — sglang's
ROCm wheel reports `0.0.0`, and falling back to the sha made the built-engine stage reject a
perfectly good image (issue #636).

The `detect` command is a checked claim too (issues #616, #605). `engine_runner` runs every
step under `set -o pipefail`, so a reader that exits early (`grep -q`, `| head -1`) makes the
writer take SIGPIPE and the pipeline report 141 — which declared a perfectly healthy
`strata`/`rocm` binary "missing". `tests/test_engine_detect_safety.py` reads the COMMITTED
params rather than the skill text, so a regeneration that drops the fix is caught as well: no
cell's `detect` may pipe into an early-exiting reader, every cell that declares a binary must
actually execute it (a `detect` that echoes the pin proves the pin, not the installation), and
`strata`'s `detect` is `{binary} --version` against a flag its `binaries.json` documents — no
pipe at all. `tests/test_engine_skills_pipefail.py` holds the no-pipe form and refuses a
`detect` that prints the short pin instead of a version.

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

A publish is a step of EVERY push run, including a same-repo `pull_request` run (measured: run
38121659510 published `llama-cpp:23b0202a-0211d...-cuda`). A FORK head cannot publish — its
`pull_request` token is scoped to the base repository's packages read-only, and GitHub refuses
the write — so `push()` turns exactly that refusal (`WRITE_DENIED`, and only when
`GITHUB_EVENT_NAME=pull_request`) into a loud skip: a `::warning title=publish skipped::`
annotation plus a `SKIP publish <ref>: pull_request token cannot write …` line, exit 0, while
the image stays built and post-build tested and the run that lands the change publishes it
(issue #155). Every other failure — a denial on a push run, a network error, a bad tag, an
image that fails its own version test — still fails loudly. The policy lives in the script,
never in a scenario-scoped workflow `if:` (`tests/test_ci_images.py::test_no_ci_step_or_job_is_skipped`
forbids those), and `tests/test_ci_publish_scope.py` drives `push()` with the literal denial
line from the run that exposed it.

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
delta (`scripts/engine_deps.py`) and regenerates the Dockerfiles; the same work is available
one step at a time as `make engine-bump-plan` (which engines moved upstream, from
`git ls-remote` only), `make engine-derive ENGINE=<id> [SHA=]` (build params from the
upstream tree, no model in the loop) and `make engine-bump ENGINE=<id>` (pin + derive +
apply + regen), with `make engine-bump-daily` running the whole moved set. `engine-bump-rebase`
keeps those PRs current. `scripts/engine_bump_sync.py` is the shared PR-sync logic and
`scripts/engine_params_derive.py` derives build parameters from the upstream tree without a
model in the loop.

A package the new pin added reaches the image only through the skill (issue #186).
`dependency_delta()` compares the watched `requirements*.txt` / `pyproject.toml` /
`Dockerfile` at the old and new sha and reports four lists — `python_added`, `apt_added`,
`python_removed`, `apt_removed` — plus `python_covered`, true when the install already runs
`pip install -r` / `uv pip install -r` or installs `pyproject.toml`. A covered Python package
needs no new line (the existing line reads the file at the new pin) and an uncovered one is a
`hard_fail` that names it, never an invented pip line. Newly added apt names are appended to
every front-matter `apt: [...]` line the skill already has (both backends receive them,
because the upstream Dockerfile did not say which backend they belong to) and
`generate-engine-params` copies them into that engine's Dockerfile only; a skill with no
`apt:` line hard-fails instead. `make engine-bump` prints one
`[engine-bump] DEPS python_added=… apt_added=… python_removed=… apt_removed=…` line when any
list is non-empty and `.github/workflows/engine-bump.yml` carries it into the PR body. A
dependency hard-fail does not abort the bump: the pin still moves, the PR still opens, and CI
goes red until a person fixes the skill.

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

## Scanner images

`containers/scanners/<id>/Dockerfile` is the only way a scanner reaches this repository
(issue #714). A scanner installed at scan time is a mutable tool on a mutable base with
network access while it judges the tree, so each one ships as its own image: the base is
pinned by digest, the scanner to an exact version (`ARG TRIVY_VERSION=…`, `apk add
"trivy=${TRIVY_VERSION}"`), and the published tag is the Dockerfile's own content hash
(`ghcr.io/<owner>/llgenie/<id>:<12-hex>`), the convention `scripts/ci_images.py` already
uses. `scripts/scanner_image.py` owns `digest` / `ref` / `build` / `test` / `publish` /
`write` / `check`; `make scanner-digests` rewrites `containers/scanners/digests.json` from
the Dockerfiles, `make test-scanner-image SCANNER=<id>` proves the image prints the version
its Dockerfile pins, `make publish-scanner-images` builds linux/amd64 + arm64 and pushes the
hash tag, and `make check-scanner-images` (in `make ci-unit`) fails a floating base, a
missing version pin or a stale `digests.json`. No scanner needs a secret. In CI,
`ci.yml`'s `scanner-images` job runs `make ci-scanner-images` — build and version-test every
scanner on every run, publish on a push run only, with the policy in the script rather than a
scenario-scoped `if:`.

## The scan pipeline

`.github/workflows/security-scan.yml` is its own daily pipeline, never a PR or push check
(issue #738). `scripts/security_scan.py` is the one place a scanner is invoked, and every
step is a make target, so the workflow, a developer and CI run the same command:

- `make check-security-scan` — the first step of the `scan` job: `data/security-policy.json`
  is well-formed, every scanner the policy expects is in `digests.json`, and the workflow
  carries **no** `pull_request:` / `push:` trigger. A scan that gated those events reddened
  the pipeline forever on pre-existing advisories (measured: run 40525155122 failed on
  `certifi`, `filelock` and `urllib3` — transitive pins nothing here bumps), so the trigger
  coming back is itself a finding.
- `make security-scan-all` (or `make sbom` and `make security-scan TOOL=<id>`) — Syft writes
  `security-reports/sbom.cdx.json`, then Trivy, Grype and Semgrep run from their pinned
  images. `security-reports/` is git-ignored: reports are run output, never tree content.
- `make security-verdict EVENT=<event> [ENFORCE=pr]` — applies the policy. `fail_on` is
  `critical` + `high`, `require_fix` is true (an advisory with no fixed version is recorded,
  never blocking), and `enforce_events` names the only events that may gate (`schedule`,
  `workflow_dispatch`); any other event, and an explicit `ENFORCE=pr`, is report-only.
- `make security-issues SLUG=… RUN_URL=…` — files or updates ONE tagged issue per
  (advisory, package), keyed by an HTML comment marker so a re-run updates instead of
  duplicating, and closes a finding that is no longer reported (`scripts/security_issues.py`,
  issue #716).
- `make security-bumps SLUG=…` — the owner of a red scan (issue #738): derives each
  package's floor as the maximum of the scanner's own `fixed` versions, writes
  `tools/security-floors.in` once, regenerates the compiled pins through the one generator
  (`make -C tools generate-requirements` / `-dev`), and opens ONE PR on `fix/security-floors`
  with a `closes #<n>` line per matched tagged issue. A floor still unsatisfied after the
  regeneration opens no PR and exits non-zero.

The `guard` job runs before any scanner and allows the owner, `github-actions[bot]` on a
same-repo head, and a collaborator with write; anyone else is refused. The manual form takes
`tools` (`all` or one scanner) and `enforce` (`full`, or `report`).

## Supply-chain pins

Every GitHub Action is pinned to a full 40-character commit SHA, with the tag kept as a
trailing comment (`uses: actions/checkout@<sha> # v4`) so the line stays reviewable
(issue #719). `scripts/pin_actions.py` reads every `uses:` in `.github/workflows/**` and
`.github/actions/**`: `make check-actions` (in `make ci-unit`) fails a non-local ref that is
not a 40-hex SHA, `make actions-report` prints every ref with its pin state and tag, and
`make update-actions` re-resolves each tag to its current commit and rewrites the workflows —
the only place an Action's pin moves. A local reference (`./.github/actions/docker`,
`./.github/workflows/pipeline.yml`) is this repository's own content at the commit being run
and is therefore exempt.

`renovate.json` is the dependency and base-image update config, and its properties are a gate
rather than a preference (issue #718). `scripts/check_renovate.py` (`make check-renovate`, in
`make ci-unit`; `make renovate-report` prints the rules) enforces the invariants the
repository depends on:

- **one merge path.** An `automerge: true` rule must also set `automergeType: pr` and
  `platformAutomerge: false`, and automerge is restricted to `patch` / `pin` / `digest`
  Python pins — so CI's `auto-merge` job remains the only thing that lands a PR.
- **the pinned files stay compiled.** `pip_requirements` matches only `requirements*.in`
  and `pip-compile` only the generated `.txt`, so a Python bump edits the source of truth and
  recompiles it; a `.txt` treated as a source is a finding.
- **generated and vendored files are untouchable.** `ignorePaths` carries `data/models.json`,
  `containers/engines/dockerfiles/**`, `containers/engines/params/**`,
  `containers/scanners/digests.json` and `containers/ci-variant/**`.
- **GitHub Actions are not Renovate's.** A `github-actions` rule is disabled: they move
  through `make update-actions` with the tag diff reviewed.
- **a Dockerfile bump reaches an image build.** `ci.yml`'s `pull_request` trigger carries no
  `paths:` / `paths-ignore:` filter and it declares an engine-image job, so a base-image PR
  builds the engine images instead of skipping them.

## Data

`data/` holds nine files, each generated or vendored, each with a make gate; the rendered
trend matrix lives under `tests/fixtures/`:

- `data/models.json` is a copy of trending-local-llms' registry, **normalised on the way in**
  (issue #687) and replaced wholesale by the weekly `registry-sync` PR (`make sync-registry`,
  which writes only when the upstream copy changed). `normalise()` keeps every upstream row —
  upstream's `models[]` holds distinct entities (a base model, a finetune, an MLX conversion, a
  run on one box) and its README lists each, so rows are never folded — restricts `formats` to
  `FORMAT_VOCAB`, states the format a row's own repo/id names when nothing in the vocabulary is
  left (upstream started writing model names into `formats[].name`, which no consumer can act
  on), and drops a duplicated row id; every departure is printed by the sync. The 2026-10-27
  store carries 112 models. `scripts/registry_keys.py` (`make check-registry-keys`, part
  of `make check-registry`) fails a sync that loses a model, a key, an engine with a
  measurement for that model, a list entry, a stated footprint or a tracked post — the
  vendored copy is additive only. Identity is what the PRODUCT consumes (issue #668): a
  measurement is compared by its post's `/status/<id>`, store-wide, never by its
  `(engine, hardware)` label, so upstream refining a hardware string, re-attributing a post
  to a split model row, upgrading a profile link to the real status URL or rebuilding the
  derived `engagement.seen_posts` placeholder no longer reads as a loss (that label rule froze
  the sync for 13 days, #534). A surviving post whose t/s was corrected downward, and a
  decreased engagement counter, are printed as `NOTE:` with both numbers and do not fail —
  they remove nothing from the ranked set. A format is identified by the FORMAT VOCABULARY
  (issue #698): `_real_formats()` keeps only the `formats[].name` values in `FORMAT_VOCAB`,
  imported from `scripts/sync_registry.py` — the normaliser that drops the names upstream
  writes there as model or recipe text ("Ornith 1.5") and states the real format instead — so
  the guard cannot read its own normalisation as a loss (ten such names reddened the first
  normalised sync), while a real format that goes away (`GGUF` → nothing) is still a `LOSS`
  and is still named. Widening the vocabulary widens the guard in the same edit.
- `data/model_contract.json` and `data/MODEL_CONTRACT.md` are the store's own contract —
  JSON Schema 2020-12 plus its prose twin — vendored byte for byte by the same
  `make sync-registry` and written only when they change, so a contract edit arrives as a
  diff of the contract instead of a shape change buried in the store (issue #694).
  `make check-registry` (`scripts/sync_registry.py check`) validates the store against that
  **vendored** schema and reads every rule from it: the top-level and per-model `required`
  keys, the model `id` pattern, the engine-name `propertyNames.pattern`, an engine entry's
  `required` keys and its `backend` enum, `formats.minItems` and a format entry's `required`
  keys. A contract that adds a required key is therefore honoured on the next run without
  touching llgenie, and a store with no vendored contract is refused, naming
  `make sync-registry`. That subset is exactly what the contract uses: a full JSON-Schema
  engine would be a `jsonschema` dependency the repository cannot add, because it is absent
  from `tools/requirements*` and the test image, and a fork-head `pull_request` token cannot
  publish a new image (#651) — so the rules outside the subset are reported on #694, never
  silently skipped. The contract leaves `formats[].name` a free string, which is why the
  format rule above is the guard's own, not the schema's.
- `data/trending-quant-catalog.json` is generated from the real registry and the live Hub
  (`make sync-quant-catalog`) and checked by `make check-quant-catalog`. Every planned cell
  obeys `plan_download()`'s own repo rule (`_repos_for`): an `mlx-safetensors` cell comes only
  from a repo whose name marks MLX, a `safetensors` cell only from one that does not, and an
  own-checkpoint engine gets a cell only for the family it really serves (`strata_serves()`,
  which is why Strata is not attached to every model it was measured on). Measured on the
  2026-10-27 store, twelve cells across MLX, vLLM, Strata and llama.cpp pointed at a download
  the engine cannot load, so the table offered what `plan_download()` refused (issue #750).
  The check is only a gate if its exit status reaches `make`, and it does (issue #701): the
  generator's `__main__` raises `SystemExit(main())`, so a committed table that differs from
  what the generator produces fails `ci-unit` and the `registry-sync` job instead of printing
  `FAIL: … is stale` and exiting 0. `tests/test_script_exit_codes.py` holds the whole class
  by parsing every `scripts/*.py`: a `__main__` that calls `main()` bare while `main()`
  returns a value is a finding, and a `main()` that returns nothing is not.
- **What "differs" means is bounded by what a regeneration can honestly prove** (issue #736).
  `scripts/gen_trending_quant_catalog.compare()` fails on a row the committed table HAS and
  the generator no longer produces — a plan gone, a plan whose repo/files/size/link changed,
  an engine's arch list changed, or a table rendered for another registry — and only NOTES
  what the live Hub re-reads: `mlx_repos()`/`tensorfold_repos()` query a `sort=downloads`
  search, so the same 14 plans came back in a different order for
  `qwen3.8-flash-next-125b`/MLX and the gate went red on `main` itself, blocking every PR for
  a reason no PR caused. A reorder or a newly published conversion is recorded by the next
  `make sync-quant-catalog`; the note says so and the exit code stays 0.
- `data/security-policy.json` is the scan's failure and issue policy (issues #715, #738):
  `fail_on` (`critical`, `high`), `pr_fail_on` (empty — a report-only run gates nothing),
  `enforce_events` (`schedule`, `workflow_dispatch`), `require_fix`, and
  `issue_severities`. `make security-verdict` applies it, `make security-issues` files from
  it, and `make check-security-scan` / `make check-security-issues` refuse a policy that
  would gate a push or a pull request, or disagree with the label roster.
- `data/strata_models.json` is written from Strata's `setup.py` at the skill's pinned
  commit (`make sync-strata-models`, checked by `make check-strata-models`; the pin is
  `v0.2.7@3f6d9c28` today). A family is either Hub-hosted — `repo` + `revision` +
  `subdir` and no `hub` key — or explicitly not-Hub: `hub: false` with no repo, never both
  and never neither. `check` runs `family_shape_problems()` first, so a malformed map is
  named by family and defect instead of surfacing as a 100-line diff; WHICH families are
  not-Hub is the pinned `setup.py`'s decision (`nvfp4` at v0.2.4), never a list in a test.
  `tests/test_strata_download.py` (the `make test-strata-live` tier) derives the expected
  not-Hub set from the pin it just fetched and asserts `strata_files` REFUSES such a family
  by name instead of building a URL from nothing, while `tests/test_strata_missing_hf.py`
  locks the SHAPE hermetically — it used to assert the v0.1.43 contents, so it reddened the
  *correct* v0.2.4 bump on `nvfp4` (issue #643, PR #605).
- `data/engine-skill-gap.json` and `data/unsupported-engines.json` are the shipped /
  known-unsupported / new-and-unresolved engine picture (`make render-engine-skill-gap`,
  `make check-engine-skill-gap`; `make engine-skill-gap`, `make engine-skill-gap-md`,
  `make spawn-engine-skill-issues` report and file work from it). On the 2026-10-27 store the
  census is 42 engines, 16 skills: 16 shipped (4 with no image), 26 known-unsupported, 0
  unresolved — the sync's 18 new engines each carry a dated, reasoned entry read from that
  project's own README, so a new engine is a decision on the record rather than a silent gap
  (issue #750).
- `data/trending-README.md` is the vendored upstream README the "Most loved" order comes
  from. `make check-registry` also checks its links, and it asks the question the right way
  (issue #690): a Hub model page is checked at `/api/models/<org>/<repo>` — the endpoint the
  token authenticates — and every request goes through `hf_auth.hub_open`, so a 429 waits the
  Hub's own window instead of reading as a dead link, a 5xx/transport failure retries, and a
  401/403/404 is definitive on the first attempt. Before that the check sent the token to the
  model's HTML page, which the Hub answered with 429, and 18 live links read as dead.
- `tests/fixtures/trend-list-matrix.json` is the rendered trend matrix
  (`make render-trend-list-matrix`, checked by `make check-trend-list-matrix`).

## CI

`.github/workflows/ci.yml` is the entry. Its triggers are `pull_request` on `main` and `push`
on `main` (a merge), and deliberately carry no `paths:` / `paths-ignore:` filter — a
Dockerfile bump must build the engine images, and `make check-renovate` fails if that stops
being true. Its jobs are `guard`, `ci-images` (publish the test and OpenSpec images on a new
hash, never rebuild per job), `scanner-images` (`make ci-scanner-images`), `engine-base`,
`engine-matrix` (the committed params, filtered by `CHANGED=<base>` to the images a PR
touched), `engine-image` (one parallel job per engine x backend), `engine-published-test`
(pull each published image back and run `make test-published-engine` on it), and `linux`,
which calls `pipeline.yml` — the reusable verification pipeline. There is no macOS caller: issue
#870 removed the group, because the hosted macOS pool on this account is not reliably issued
(probe `40741670180` queued all three labels for 14 minutes each with `runner=NONE`; 54 macOS jobs
were cancelled with no runner ever assigned), so a PR that depends on a macOS row depends on a queue
that may never reach it. `pipeline.yml` keeps its `runner` input, so macOS can be restored by adding
a caller back; until then a macOS-path change needs hand review.
`pipeline.yml` runs one job per `make ci-<job>` target — `lint` (`ci-lint`), `unit`
(`ci-unit`), `install` (`ci-install`), `agents-read` (`ci-agents-read`), `openspec`
(`ci-openspec`), `cpu-health` (`ci-cpu-health`) and `top-tier` (`ci-top-tier`). `ci-openspec` runs
`make openspec-validate-all` and then `make openspec-tasks-check`: the structure of EVERY
active change is validated, because the job used to name one hardcoded change
(`NAME=ci-pipeline`), so the change a commit actually touched could land without its
structure ever being checked (issue #156). `linux-published` calls `published.yml`, whose
`install-published` job runs `make ci-engines BACKEND=<b>` for `cpu`, `cuda`, `rocm` and
`vulkan` against the images the `engine-image` jobs published.

`make ci-unit` is the gate bundle, not just the suite: `bash-check`, then `make test-unit`,
`skills-validate` (twice — the second time against `data/models.json` and
`data/unsupported-engines.json`), `check-registry`, `check-strata-models`,
`check-quant-catalog`, `check-trend-list-matrix`, `check-engine-skill-gap`,
`check-engine-params`, `check-engine-source`, `check-wiring`, `check-secret-output`,
`check-docs`, `check-dispatch-forms`, `check-pr-hygiene`, `check-issue-bodies`,
`check-pr-authors`, `check-workflows`, `check-scanner-images`, `check-security-scan`,
`check-security-issues`, `check-security-bumps`, `check-security-bot`, `check-actions`,
`check-renovate`, `check-agent-skills`, `check-agent-model`, and the issue-bot gate pair
(`issue-bot-gates`, `issue-bot-gates-check`). Every gate added to this list must also be
classified FAST or `DEFERRED` in `scripts/issue_bot_gates.py`, or `make test-unit` fails.

The unit gate no longer races its own pipeline (issue #672). `tests/test_ci_publish_order.py`
resolves the install plan and asks GHCR whether each cpu tag exists, which is true on `main`
but false by construction on an engine-bump PR — the tag it resolves is created by the same
run's parallel `engine-image-*` job. `_deferred_engines()` now defers an engine whose
`containers/engines/params/<id>.json` differs from `origin/main` (or has no copy there), the
test checks every tag this change did not repin, and it prints the engines it deferred with
the gate (`make ci-wait-engine-images`) that covers them; no git on `PATH` means nothing is
deferred, i.e. the previous, stricter behaviour.

The test and OpenSpec images are hash-tagged artifacts, not per-job rebuilds: `make test-image`
and `make openspec-image` pull the published hash of their Dockerfile (plus lockfiles) and
build it locally only when that hash is not on GHCR yet; `test-image-pull` and
`openspec-image-pull` are what CI calls, and they fail rather than build. `make agent-image`
and `make agent-image-pull` pull `ghcr.io/<registry>/llgenie/agent:latest` — the tag
`publish agent` points at the current content hash, including when that hash was already
published — and the pull form fails rather than builds. `make agent-image-ref` prints that
`:latest` ref.
`make publish-ci-images` is the `ci-images` job (test + OpenSpec, amd64 + arm64, only the
hashes not yet published), `make ci-image-refs` prints the three refs, and
`make agent-image-push-check` proves the GHCR credential may write before a 60-minute agent
build starts. `make ci-free-disk` frees the runner's disk for the large engine images, and
`make test-clean` removes left-over or stopped test containers.

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
`name:`, every `workflow_run` roster names workflows that exist and leaves none unwatched), `make check-dispatch-forms` (a dispatchable workflow documents its inputs and
stages), `make check-wiring` (every script/test reachable from a target CI runs),
`make check-docs` (every `##` make target is in `README.md` or a `docs/` page the README
links, every `agent-wiki/` note names its issue and PR and has its own index row in
`docs/changes.d/` — `CHANGES.md` is that index rendered, so no two changes edit one line
(issue #934) — and `README.md` carries no change history), `make check-pr-hygiene`,
`make check-issue-bodies`,
`make check-pr-authors`, `make check-secret-output`, `make check-engine-source` (a
`prebuilt: false` cell must run a real build, with its tracked exceptions reported),
`make check-actions` and `make check-renovate`, `make check-scanner-images` and the
`check-security-*` roster, `make check-agent-model` (the agent image's model pin equals the
one `scripts/agent_model_pin.py` declares), `make check-agent-skills` (every bot leg
preloads `.hermes/skills/<name>`, the skill exists with `Inputs`/`Output`/`Rules`, and the
inline prompt is a pointer), the `make secret-scan` / `make secret-scan-self-test` pair
(`make secret-scan-history` is the same scanner over git history, host-only by design), plus
`make bash-check` (`scripts/check_bash.py`, the bash-5 parity check that resolves the
Makefile's shell) and `scripts/check_python.py`, which `tools/Makefile` runs to keep the gguf
venv on Python 3.11. All of them run inside `make ci-unit`. Every gate has a report target
that prints what it read without deciding anything — `make workflows-report`,
`make wiring-report`, `make docs-report`, `make changes-index-report`, `make pr-hygiene-report`,
`make issue-bodies-report`, `make pr-authors-report`, `make secret-output-report`,
`make model-pin-report`, `make agent-skills-report`, `make engine-source-report`,
`make dispatch-forms-report`, `make actions-report`, `make renovate-report` — so a red gate
can be read before it is edited.

`make check-wiring` decides both directions from the same file. A recorded exception
(`tests/fixtures/host-only-wiring.json`) is stale in one direction once CI reaches the
document, and stale in the OTHER once the target's `##` help line stops claiming CI coverage:
the `targets` half of that fixture exists only for a help line that was corrected instead of
wired, so an entry whose claim survived — or vanished — is dead prose that hides the next
drift, and the gate names it (`test-install-ci`'s entry said its help line no longer claimed
the pipelines ran it while the help line still did, issue #239; the rule is locked by
`tests/test_wiring.py`, issue #657). The gate's `json` subcommand emits `reachable`,
`named_by_target` and `workflow_targets` as sorted lists, never a `set` (issue #395).

The same gate asserts the reverse `.PHONY` direction (issue #883): every key must name a target
with a recipe, an inline `;` command, or at least one prerequisite (a declared alias like
`loop: loop-harness`). A key whose recipe is gone is a permanent green no-op — because the name is
declared phony, `make <name>` prints `Nothing to be done` and exits 0, where the same name with no
declaration fails `No rule to make target` — so `scripts/check_wiring.py` names every offender in
one pass and `make wiring-report` prints the can-run / no-target / runs-nothing counts.

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
the same kind of scratch from `scripts/issue_dedup.py`, and the registry review's
`registry-review-in.md` / `registry-review.md` are the same from `scripts/registry_review.py`;
those workflows push and commit nothing, so they never reach a tree. The scan's reports land
in the git-ignored `security-reports/`.

| Workflow | Cron | What it does |
|---|---|---|
| `issue-bot.yml` | `23 6 * * *` | implements ONE labeled/ready issue per run as a reviewable PR; a manual dispatch with no issue number picks one itself, the implementation is measured from the changed tree (not the exit code), the PR body is built from the run's `pr-body.md`, and a close verdict queues the canonical issue it cites (`scripts/issue_implementer.py`, issue #521). Only a CLOSE is a decision: `agent:refined` is a marker that a restatement exists, so a refined issue stays in the picker's queue instead of becoming invisible to the implementer (issue #522). After "did the tree change" and BEFORE the push, it runs `make issue-bot-gates`, so a bookkeeping red (an unticked `- [ ]`, a stale target list, a wiring count) is caught in seconds on the host instead of a CI round trip plus a fix-bot hour (issue #475) |
| `issue-refiner.yml` | `43 * * * *` | reviews one issue and refines or closes it with cited evidence (`scripts/issue_refiner.py`) |
| `issue-dedupe.yml` | `51 */6 * * *` | four times a day: picks ONE pair of similar **unclaimed** open issues, older as canonical (`scripts/issue_dedup.py`), has the agent decide `DUPLICATE: #<older>` with `EVIDENCE:`, and retires the copy with that comment + `agent:duplicate` while queueing the canonical — never touches a claimed issue, never opens a PR (issue #553) |
| `fix-bot.yml` | `17 * * * *` | repairs a red PR branch — including one whose head is the repository's own fork — re-runs the gate, pushes only when green; its sweep (`scripts/fix_bot_sweep.py`) treats a PR with no checks at all as not-red rather than a crash (issue #496). A `workflow_run` on a failed `CI` `pull_request` run resolves that run to its PR with `make fix-bot-resolve` (the same resolver as the merge gate, asked with `--allow-none`: an empty `number=` is an answer, so a failure reported after its PR already merged or closed ends the job cleanly instead of red and does not become a reactor issue — issue #629) and captures the failed job's log, then dispatches the repair — so a red PR is acted on in minutes rather than at the next hourly sweep (issue #538); `rounds` defaults to 5 and the job allows 260 minutes (issue #539) |
| `rebase-bot.yml` | `29 */6 * * *` | drains every eligible PR onto `main` in one run, bounded by `max_prs`; decides from a computed merge state, hands a conflict to the agent and checks the resolution structurally (a recipe's TAB, the wiring guard, lint) against the checkout it mounted, aborts a stopped rebase so the tree returns to `main`, and pushes `--force-with-lease` to the PR's own head remote |
| `code-review-bot.yml` | `31 7 * * 1` | files issues for findings in the tree and the pipelines (`scripts/code_review.py`) |
| `security-scan.yml` | `5 4 * * *` | the daily vulnerability pipeline (Trivy + Syft + Grype + Semgrep, from their pinned images), never a PR or push check; one run is `make check-security-scan` -> `make security-scan-all` -> `make security-verdict EVENT=…` -> `make security-issues` -> `make security-bumps`, with the reports uploaded as SARIF and as an artifact (issues #715, #738) |
| `security-bot.yml` | `9 5 * * *` | turns ONE `auto-fixable` vulnerability issue into a green PR (`make security-bot`), on a labelled issue or the daily schedule: the pin is parsed out of the issue body, the edit lands on the one file that owns it, `make lint check-wiring check-docs check-security-scan` must pass before the push, and a finding it cannot place (a container advisory, a package pinned nowhere) becomes a comment instead of a guessed PR (issue #717) |
| `registry-sync.yml` | `19 5 * * 1` | byte-copies the upstream registry, its README and its model contract (`data/model_contract.json` + `MODEL_CONTRACT.md`), validates every engine skill with `ALLOW_NEW_ENGINES=1` so a store that first names an engine llgenie does not ship is CARRIED rather than fatal (issue #683), opens one tracking issue per new engine (`make spawn-engine-skill-issues`), states what the store changed in ONE issue even when a gate reds (`make sync-change-issue`, `scripts/registry_change_issue.py`, issue #704), regenerates the derived tables and opens a PR; `ci-unit`'s `make check-engine-skill-gap` keeps that PR red until each engine ships a skill or gets a dated decision. The spawn step runs with `always() && steps.diff.outputs.changed` and re-checks the store diff inside its own recipe before `make`, because the store that names a new unskilled engine is exactly the store whose check step reds and a `success()`-gated spawn suppressed the one work item that explains how to un-red it (issue #758); the PR step keeps its change-only condition, so a file whose checks did not pass is never pushed |
| `registry-sync-review.yml` | `55 * * * *` | reviews a **green** sync PR into ONE work item (issue #709): `make registry-review-brief` checks out the sync PR's head and, offline, decides `action=review|skip` from the PR's own check buckets and renders the VRAM selection table — per `(arch, vram, ram)`, the models the trend list shows and the server `rank_engines()` puts first with its t/s, with `slower-than-class` / `no-engine` / `unmeasured` / `empty-tier` findings. Only on `review` does it build the agent image, prove the shell keys and run the `registry-sync-review` leg (`make registry-sync-review` -> `registry-review.md`), then `make registry-review-publish` files ONE issue labelled `agent:implement` keyed by the store's `generated_utc`; an hourly run with no green PR costs nothing |
| `engine-bump.yml` | `53 6 * * 1` | pins every engine skill to its upstream release (carrying the dependency delta's `DEPS` line and any hard-fail into the PR body), then reviews the derived build params against that engine's own documentation at the new pin (`make engine-params-review-brief` -> `make engine-params-review` -> `make engine-params-review-apply`) and appends the review section to the PR body; the review is `continue-on-error`, so a failed or empty review still opens the PR and says so (issues #583, #186) |
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
`deepseek/deepseek-v4-flash-0731`) and are covered by
`tests/test_bot_pipeline_isolation.py` (no shared cron slot, no shared concurrency group).

Each leg's contract is a Hermes **project skill** (issue #577), not an inline rulebook:
`.hermes/skills/<name>/SKILL.md` — `issue-triage`, `issue-implement`, `issue-refiner`,
`issue-dedup`, `pr-fix`, `rebase-conflict`, `architecture-doc`, `engine-params-review`,
`registry-sync-review`, `agent-fetch` — preloaded with `hermes -s <name>,bot-unattended`, and
the inline prompt is a
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

The issue-bot's pre-push gate is its own module, not a Makefile recipe (issue #475).
`scripts/issue_bot_gates.py` holds `FAST_GATES` (`lint`, `check-workflows`, `check-wiring`,
`check-docs`, `check-pr-hygiene`, `openspec-tasks-check`) in order, stops at the first
failure and names it, and its `check` half is static: every other gate `ci-unit` runs must be
classified either fast or `DEFERRED` with the reason it is not re-run before a push (a new
`ci-unit` gate that is in neither reds `make test-unit`), a deferred entry that is stale or
contradicts `FAST_GATES` is a finding, and `.github/workflows/issue-bot.yml` must run
`make issue-bot-gates` between `Detect what the implementation changed` and
`Commit + push the feature branch` under the `changed == 'true'` condition. It deliberately
does not re-run `make test-unit`: the agent already ran the whole suite while writing the
change. The `check-issue-bodies`, `check-actions`, `check-renovate` and every
`check-security-*` gate are `DEFERRED` there with their reasons, so adding one to `ci-unit`
forces the classification.

Every leg is split into ordinary make targets, so a run can be reproduced by hand.
`make implement-issue` is the shared agent step (`issue-implement` skill), with
`make issue-bot-dispatch` (cap -> pick -> claim -> `issue.md` + branch),
`make issue-bot-triage` (`issue-triage` skill -> `triage.md`), `make issue-bot-verdict`
(applies the verdict), `make issue-bot-changed` (did the tree actually change) and
`make issue-bot-open-pr` (the PR, refusing a body with a missing part); `make issue-bot-image`
is that leg's image alias. The refiner is `make issue-refiner-pick` / `make issue-refiner-apply`
(its `DRY=1` pick prints the issue it chose and writes nothing into the checkout it previews,
issue #352), the dedupe sweep `make issue-dedup-pick` / `make issue-dedup-apply`, the rebase
leg `make rebase-bot-sweep` / `make rebase-bot` / `make rebase-bot-agent` /
`make rebase-bot-abort`, the fix leg `make fix-bot-sweep` / `make fix-loop` /
`make fix-loop-image` / `make fix-bot-report`, the review bot `make code-review-scan` /
`make code-review-file`, and the registry review `make registry-review-brief` (deterministic,
`action=review|skip` + findings) / `make registry-sync-review` (the agent leg) /
`make registry-review-publish` (the only GitHub writer, `DRY=1` previews). `make bot-sync-main`
resets a new branch to latest `main` before
work and `make bot-sync-branch` rebases a PR branch onto it before a repair (exit 2 means the
rebase conflicts and is left to the rebase-bot).

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
loud, never a skip; `make require-env KEYS="…"` is its target) and forwards credentials
through the Makefile's `AGENT_SHELL_KEYS` / `$(AGENT_SHELL_FORWARD)` seam;
`make hermes-smoke` proves the model can call a tool, `make agent-shell-keys-check` proves
every forwarded credential is visible in the agent's own shell (through
`scripts/agent_shell_keys_check.py`), and `scripts/scrub_log.py` (`make scrub-log`) is the
only thing that prints an agent transcript. The one web reach is `make agent-fetch` (Firecrawl
key, text to `OUT`), with `make search-smoke` as its loud proof and `make web-coverage` /
`make issue-evidence` reading it from the tree.

Coordination lives in the tree, not in the workflows: `scripts/bot_claims.py` says which bot
is already working a subject, `scripts/rebase_bot_sweep.py` (`make rebase-bot-sweep`) and
`scripts/fix_bot_sweep.py` decide the one PR a sweep acts on, `scripts/issue_cleaner.py`
(`make issue-cleaner-scan` / `make issue-cleaner-apply`) finds an open issue a merged PR
already implemented, and `scripts/issue_dedup.py` decides which pair of issues the dedupe
sweep compares.

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

`make test-unit` discovers every `tests/test_*.py` through `scripts/unit_tests.py` (171
files today); a file is in the gate the moment it exists, and an exclusion is a dated entry
in `tests/fixtures/unit-suite.json`. `make test` runs the named `groups.fast` subset from
the same roster rather than a hand-kept list of files. The live gates are separate targets
(`test-install`, `test-health`, `test-engine`, `test-published-engine`,
`test-native-engine*`, `test-top-tier*`, `test-hub-live`, `test-strata-live`,
`test-engine-bump-live`) and are never skipped: a missing prerequisite fails loudly.
`make test-engine-bump-live` runs in `engine-bump.yml` after that workflow writes the new
TensorFold pin and parameter list, and not in the `ci.yml` unit job. On an
Apple-Silicon host `make test-health` is the real GPU/Metal proof — it launches
`~/bin/llgenie` against the host's Metal `llama-server`; on Linux it answers "hi" through
the llama.cpp engine image. The native-Metal gates (`test-native-engines`,
`test-native-engine-serve`, `test-native-engine-light`, `test-interactive-tensorfold`,
`test-interactive-tensorfold-ci`) exist only on an Apple-Silicon host, where
`make test-native-engines` installs each native-Metal engine (litert, mlx, ollama,
tensorfold) in its own environment; every other host tests those engines in their images.

`make loop` (`scripts/loop_harness.py`) runs the same stages, in this order, and fails
closed: `image` (`make test-image`), `download` (`make download-test-model`), `lint`,
`agents-read`, `unit`, `install` (`make test-install-host`), `health`, `top-tier`,
`top-tier-serve`, `test`, `openspec`, `openspec-tasks` (`make openspec-tasks-check`) and
`clean` (`make test-clean`). The `openspec` stage validates EVERY active change
(`make openspec-validate-all`) unless `NAME=<change>` names one, in which case it validates
that one; the old default was a hardcoded change name, so the change a commit touched was
never the one checked (issue #156, locked by `tests/test_openspec_gate.py`). The lint stage
is `make lint` (`scripts/lint_linefeeds.py`): every tracked text file ends with a trailing
newline **and** every markdown heading is preceded by a blank line, so sections read as
distinct blocks; `make lint-fix` appends the missing trailing newline reproducibly. The test
environment is `make test-env` (Linux pulls the `llgenie/test` image; macOS builds the 3.11
gguf venv and puts `uv` on `PATH`).

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
`tests/test_engine_detect_safety.py` (no committed cell's `detect` pipes into an
early-exiting reader under `set -o pipefail`, every cell with a binary actually runs it, and
`strata`'s detect is a documented `--version` with no pipe — issues #616, #605),
`tests/test_engine_skills_pipefail.py` (no `detect` prints the short pin instead of a
version),
`tests/test_engine_gate_strict.py` (no flag answered is red, the device exemption is a named
list with a reason, and a version must look like a version — `0.0.0` and a log stamp are
not one),
`tests/test_engine_force_rebuild.py` (`FORCE=1` passes `--no-cache` and reads no registry
cache, the shared base is forced too, `build-engines` forwards it into every row, and a
publish carries the hash tag, `:<arch>` and a `:latest` claimed by one variant — with a
missing `:latest` a note and a drifted one a failure),
`tests/test_ci_publish_scope.py` (a fork `pull_request` publish denial is the loud skip, and
every other failure still fails),
`tests/test_ci_publish_order.py` (an engine this change repinned is deferred to
`ci-wait-engine-images`, the rest are still checked, and no git means nothing is deferred —
issue #672),
`tests/test_engine_build_workflow.py` (the sweep is dispatch-only, the guard runs first, the
matrix comes from `make engine-build-matrix` and the committed params rather than a roster,
every row is built and then verified, publishing is opt-in, and `force` reaches the build
step only),
`tests/test_engine_source_guard.py` (a `prebuilt: false` cell with no build is a finding, and
a tracked exception is reported rather than failing the gate),
`tests/test_issue_bot_gates.py` (every `ci-unit` gate is classified fast or deferred, a fast
gate is wired and `.PHONY`, and the workflow's gate step sits between the change detection
and the push — issue #475),
`tests/test_agent_legs_quoting.py` (every scrubbed leg survives `make -n` with both quotes
balanced and its whole `-s` list intact),
`tests/test_wiring.py` (a target CI never runs needs a dated decision and that decision goes
stale both ways, a help line that claims CI coverage is guarded, the `json` subcommand is
valid JSON with its three keys, and every real target is declared `.PHONY` — issues #239,
#392, #395, #657),
`tests/test_openspec_gate.py` (`ci-openspec` runs the all-changes gate with no hardcoded
name, and the loop does the same unless `NAME` names one — issue #156),
`tests/test_registry_keys.py` (a measurement is identified by its post, store-wide, so a
relabelled hardware string, a re-attributed post and a derived `seen_posts` rebuild are not
losses, while a dropped model, engine or post still fails — issue #668; and a `formats` name
outside the vocabulary is not a lost format while a dropped real one still is — issue #698),
`tests/test_script_exit_codes.py` (every `__main__` that discards `main()`'s return value is
a gate whose status never reaches `make`, and a `main()` that returns nothing is left alone —
issue #701),
`tests/test_trend_pick.py` (the sync vendors `model_contract.json` and `MODEL_CONTRACT.md`
byte for byte beside the store and is idempotent, the check refuses a store with no vendored
contract naming `make sync-registry`, and a row missing a contract key, a bad `id`, a backend
outside the enum and a `formats[0]` with no `hf` are each refused by name — issue #694),
`tests/test_model_engine_pick.py` (an engine without a cell in the committed table is not
offered for a model the table covers, and a model it does not cover keeps live resolution —
issue #750),
`tests/test_trend_list_matrix.py` (the committed matrix is the `(arch, vram, ram)` grid, and
a listed row is either served or says why — never a blank server beside a blank reason, which
is what the `system_ram_min` floor produced while `trend_rows` asked without the RAM — issues
#669, #750),
`tests/test_hub_probe.py` (401/403 is `gated`, i.e. the file exists but this credential may
not read it, so a gated link verifies instead of reading as missing — issues #418, #750), and
`tests/test_registry_review.py` (the review's real `selection()` over a real store in a
temp dir names the highest-t/s server per card and fires on a wrong order, `brief()` answers
`action=skip` for a missing, red or pending sync PR and `review` only when every check
bucket is `pass`, `publish()` edits its own `<!-- registry-sync-review: <utc> -->` issue
instead of filing a second one, and the workflow gates every secret-spending step on
`action == 'review'` and its skill carries `Inputs`/`Output`/`Rules` — issue #709),
`tests/test_bot_scratch_ignored.py` (every bot run input at the repo root, the registry
review's `registry-review-in.md` / `registry-review.md` included, is git-ignored — it is
scratch, not repo content),
`tests/test_worktree_prune.py` (the detached-worktree match by HEAD, and a delete refusal
that splits into a one-shot retry or a keep).

The issue-body shape and the supply-chain pins have their own hermetic locks:
`tests/test_issue_body.py` and `tests/test_check_issue_body.py` (the renderer emits the six
sections in order with `## Technical` last and a tickable `## Acceptance criteria`, a
producer's marker survives as the first line, and the gate fails a producer that hand-builds
a body or an `AGENTS.md` / issue skill that lost the rule — issue #745),
`tests/test_pin_actions.py` (a floating tag is a finding, a full SHA with its tag comment
passes, and a local `./.github/…` ref is exempt — issue #719),
`tests/test_renovate_config.py` (automerge is low-risk only and never a second merge path,
no compiled or vendored file is an edit target, `ci.yml` keeps its unfiltered
`pull_request` trigger and its engine-image job — issue #718),
`tests/test_scanner_images.py` (a digest-pinned base, an exact scanner version, and a
`digests.json` that agrees with the Dockerfiles — issue #714),
`tests/test_security_scan.py` (the policy decides which events may gate, a
`pull_request`/`push` trigger is a finding, and `require_fix` keeps an advisory with no fix
out of the failure set — issues #715, #738),
`tests/test_security_issues.py` (`<!-- security-finding: … -->` round-trips, a re-run updates
instead of duplicating, and a cleared finding is closed — issue #716),
`tests/test_security_bumps.py` (the floor is the maximum of the scanner's own `fixed`
versions, an unsatisfied floor opens no PR, and the regenerated pin carries it — issue #738),
and `tests/test_security_bot.py` (one `auto-fixable` issue is selected, its pin is parsed out
of the body, and a container or unpinned finding is refused with the reason — issue #717).

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
resets/errors, `SSLError`, resolution failures, or 429/502/503/504). A subprocess that
outlives its own deadline is one of those transport shapes, not a traceback out of the seam
(issue #676): `TimeoutExpired` is converted to `returncode=124` with `timed out after <n>
seconds` in its stderr, the retry gets its own attempt, and at the bound the caller fails with
the timeout named — the `top-tier` job allows 90 minutes so the retry fits above the
38-minute stage. Any other non-zero exit is returned on the first attempt, so a bad argument
or a real regression is never retried into a green; a Hub that stays unreachable spends the
bound and still exits non-zero with the CLI's named cause (issue #399, locked by
`tests/test_top_tier_dry_run_retry.py`).

`make check-docs`, `make check-pr-hygiene`, `make check-issue-bodies`,
`make check-pr-authors`, `make check-workflows`, `make check-dispatch-forms`,
`make check-wiring`, `make check-secret-output`, `make check-engine-source`,
`make check-actions`, `make check-renovate`, `make check-scanner-images`, the
`check-security-*` roster, `make check-agent-model` and `make check-agent-skills` are the
repository's structural gates, and each has its report target (`docs-report`,
`changes-index-report`,
`pr-hygiene-report`, `issue-bodies-report`, `pr-authors-report`, `workflows-report`,
`dispatch-forms-report`, `wiring-report`, `secret-output-report`, `engine-source-report`,
`actions-report`, `renovate-report`, `model-pin-report`, `agent-skills-report`) that prints
the same census without failing. The data gates
(`check-registry` — the store against the vendored contract, then against the committed copy
— `check-registry-keys`, `check-quant-catalog`,
`check-trend-list-matrix`, `check-engine-skill-gap`, `check-strata-models`,
`check-engine-params`, `skills-validate`) run inside `make ci-unit` alongside the unit
suite.

`make check-docs` is also what keeps this repository's documentation honest (issue #678).
The README is the user guide, not a change log: a target is documented when its whole token
appears in `README.md` or in a `docs/` page the README links (`docs/BOTS.md` for automation,
`docs/ENGINES.md` for engine build/serve, `docs/SCANS.md` / `docs/SCANNERS.md` for the scan
pipeline, `docs/SECURITY.md` for the pins, `docs/RENOVATE.md` for dependency updates), every
`agent-wiki/` note must reference an issue or PR and have its own index row in
`docs/changes.d/` (one row per file, so a merge never re-dirties an open PR — issue #934), every
row must name a note that exists, `CHANGES.md` — the rendered table — must link no missing note,
`README.md` must link `CHANGES.md`, and a README heading
that carries an `(issue #N)`, a change-log title or the generated dispatch-table marker
fails. A user-facing target that is deliberately undocumented needs a dated exception in
`tests/fixtures/docs-exceptions.json`, and that entry goes stale once the target is
documented or gone.

## Adding a change

An issue is the root; the branch, the OpenSpec change (`openspec/changes/<name>/`), the
code and the PR all trace back to it. The issue body is not free prose: it carries
`## Problem`, `## Why it matters`, `## How we fix it`, `## Benefit`,
`## Acceptance criteria` (one tickable `- [ ]` per provable outcome) and — LAST — `## Technical`,
optionally with `## Not covered` between the last two, each deferred item naming its own
issue (issue #745). `scripts/issue_body.py::render` is the ONE renderer every in-repo
producer files through (`PRODUCERS` names them), and `make check-issue-bodies` fails a
producer that hand-builds a body, a body missing a section or ordering, and an `AGENTS.md`
or issue skill that lost the rule. The mapping to the PR body is fixed, so the two cannot
drift: `Problem` ↔ `Issue:`, `How we fix it` ↔ `Fix:`, `Benefit` ↔ `Benefit:`, `Technical` ↔
`Technical:`.

Work happens in its own git worktree cut from `origin/main`. The OpenSpec change is written
before the code (`make openspec-new NAME=<name>`, `make openspec-validate NAME=<name>`), each
task is ticked when verified (`make openspec-tasks-check` asserts none is left unchecked),
and the same commit carries the change's dated `agent-wiki/` note and its own index row under
`docs/changes.d/` — one row per file, and `CHANGES.md` is that index rendered by
`make changes-index`, never edited by a change (issue #934) — and, when the change alters something
a user runs, the matching
`README.md` section. The PR targets `asimov-agent/llgenie:main`, carries
`Issue:` / `Fix:` / `Benefit:` / `Technical:` and `closes #<n>`, and only Andy Holst or
Asimov Agent may author its commits (`make check-pr-hygiene`, `make check-pr-authors`).
`make openspec-validate-all` is the gate the loop and CI run — it checks the STRUCTURE of
every active change, so the change a commit introduces cannot slip past a name someone
forgot to update (issue #156). The agent drives the PR green and stops:
`.github/workflows/auto-merge.yml` squash-merges it once the run is green and the PR is
conflict-free. The agent never runs `gh pr merge` and never pushes to `main`; a reviewer
holds a PR with `do-not-merge`, and `make worktree-prune` removes the worktree and branch
after the merge.
