# feat-engine-bump-daily — spec of record

## ADDED Requirements

### Requirement: plan finds the latest upstream pin (git only)
`make engine-bump-plan [ENGINE=<id>]` MUST, for each servable engine skill,
resolve the latest upstream commit for its `ref` using `git ls-remote` only, and
report which engines moved. It MUST never move a pin backwards.

- `ref_kind: branch` → `git ls-remote <repo> refs/heads/<ref>`; `pinned` = head
  sha, `ref` unchanged.
- `ref_kind: tag` → `git ls-remote --tags --refs <repo>`, keep tags with the same
  shape as the current tag (derived regex), drop pre-releases (`rc`, `alpha`,
  `beta`, `dev`, `pre`, `post`), sort numerically, take the highest; `ref` =
  `version` = new tag, `pinned` = peeled sha.
- Highest ≤ current → skip (never backwards). Same sha → skip, logged.
- `git ls-remote` failure → 3 tries with backoff, then `lookup failed` in the
  run summary; other engines continue.
- Output: `[{id, repo, ref_kind, old_ref, old_sha, new_ref, new_sha}]` sorted by
  id. This list is the matrix for the bump job.

#### Scenario: branch skill resolves the head sha
- **Given** a skill with `ref_kind: branch` and `ref: master`
- **When** `engine_bump.plan` runs `git ls-remote <repo> refs/heads/master`
- **Then** `new_sha` is the head sha, `new_ref` is unchanged (`master`), and the
  engine is in the plan only if `new_sha != pinned`
- **Test:** `tests/test_engine_bump.py::test_plan_branch_resolves_head_sha`

#### Scenario: tag skill picks the highest stable tag of the same shape
- **Given** a skill pinned at `v0.35.1` and upstream tags
  `v0.9.7-rc1, v0.10.0, v0.9.10, nightly, v0.40.0`
- **When** `engine_bump.plan` resolves the tag
- **Then** `new_ref`/`new_version` is `v0.40.0` (highest stable `vX.Y.Z`, no
  `-rc`), and `new_sha` is its peeled sha
- **Test:** `tests/test_engine_bump.py::test_plan_tag_picks_highest_stable_same_shape`

#### Scenario: never moves backwards
- **Given** a skill whose current pin is newer than the highest upstream tag
- **When** `engine_bump.plan` runs
- **Then** the engine is skipped (not in the plan)
- **Test:** `tests/test_engine_bump.py::test_plan_never_moves_backwards`

#### Scenario: lookup failure is reported, others continue
- **Given** one engine whose `git ls-remote` fails after 3 tries
- **When** `engine_bump.plan` runs
- **Then** that engine is reported `lookup failed` and the other engines are
  still in the plan
- **Test:** `tests/test_engine_bump.py::test_plan_lookup_failure_continues`

### Requirement: pin edits only the pin keys
`engine_bump.pin` MUST change only `pinned`, `ref` + `version` (tag skills),
`verified` (UTC date), and image digests. Every other byte of SKILL.md MUST be
identical.

#### Scenario: pin edit is surgical
- **Given** a SKILL.md with a known `pinned` and `verified`
- **When** `engine_bump.pin` writes the new pin
- **Then** only `pinned`/`ref`/`version`/`verified`/digest lines differ; the
  rest of the file is byte-identical
- **Test:** `tests/test_engine_bump.py::test_pin_edit_is_surgical`

### Requirement: derive build parameters from the upstream tree (no LLM)
`make engine-derive ENGINE=<id> [SHA=<sha>]` MUST read the upstream tree at the
sha via `git show <sha>:<path>` on a `--filter=blob:none` clone and produce a
stable `findings` JSON. The same sha MUST give the same bytes. Each skill
declares which extractors apply in a `derive:` frontmatter key.

#### Scenario: derive is byte-deterministic
- **Given** a fixed sha for an engine
- **When** `engine_bump.derive` runs twice
- **Then** the two `findings` JSON documents are byte-identical
- **Test:** `tests/test_engine_bump.py::test_derive_deterministic`

### Requirement: E2 renames a cmake option automatically
When a skill uses `-DOLD=…` and the upstream tree declares
`llama_option_depr(LEVEL OLD NEW)`, the bump MUST replace it with `-DNEW=…`
keeping the value.

#### Scenario: renamed option is auto-applied
- **Given** a fixture repo with `llama_option_depr(FATAL_ERROR LLAMA_CUBLAS GGML_CUDA)`
  and a skill using `-DLLAMA_CUBLAS=ON`
- **When** the bump derives and applies
- **Then** the skill becomes `-DGGML_CUDA=ON`, params regenerate, nothing else
  changes
- **Test:** `tests/test_engine_bump.py::test_e2_rename_auto_applied`

### Requirement: E3 hard-fails on a removed cmake option
When a skill `-DNAME` (in `cmake_flags`/`hw_flags`) was an option at the old sha
and is gone at the new sha with no rename, the bump MUST record a hard-fail. The
pin STILL moves and a PR is STILL created, with the hard-fail flagged in the PR
body so a human fixes the skill (CI goes red on the build). Nothing is guessed.

#### Scenario: removed option is flagged, PR still opens
- **Given** a fixture repo where `option(GGML_X …)` was deleted between two
  commits and a skill still uses `-DGGML_X=ON`
- **When** the bump derives
- **Then** it records a hard-fail naming `GGML_X`, the pin still moves, and a PR
  is created whose body flags the hard-fail
- **Test:** `tests/test_engine_bump.py::test_e3_removed_option_hard_fails`

### Requirement: E4 mirrors upstream recipe flags
The bump MUST read the `cmake -B/-S …` line(s) in each backend's `recipe`
Dockerfile (joined across `\` continuations, `${VAR}` left as is). Recipe `-D`
flags listed in `mirror` that are missing or differ in the skill backend MUST be
auto-added/updated; recipe `-D` flags not in `mirror` are report-only.

#### Scenario: mirrored recipe flag is added
- **Given** a fixture `.devops/cuda.Dockerfile` with a multi-line
  `cmake -B build … \` invocation adding `-DGGML_BACKEND_DL=ON`
- **When** the bump derives
- **Then** `cmake_flags.cuda` gains `-DGGML_BACKEND_DL=ON`, and non-mirrored
  flags appear only in the report
- **Test:** `tests/test_engine_bump.py::test_e4_recipe_flag_mirrored`

### Requirement: E5 updates the toolchain
When the upstream `ARG CUDA_VERSION=<v>` / `ARG ROCM_VERSION=<v>` differs from
the skill's `toolchain.<backend>`, the bump MUST update it so the generator
picks the matching base image.

#### Scenario: toolchain bump is applied
- **Given** a fixture `ARG CUDA_VERSION=12.8.1` changing to `13.0.3`
- **When** the bump derives
- **Then** `toolchain.cuda` and the generated Dockerfile's base image both move
- **Test:** `tests/test_engine_bump.py::test_e5_toolchain_bump`

### Requirement: E6 renames the GPU targets variable
When the HIP CMakeLists reads `GPU_TARGETS` while the skill's `hw_flags.rocm`
uses `AMDGPU_TARGETS`, the bump MUST rename the variable.

#### Scenario: gpu targets var renamed
- **Given** a fixture HIP CMakeLists reading `GPU_TARGETS` and a skill using
  `AMDGPU_TARGETS`
- **When** the bump derives
- **Then** `hw_flags.rocm` uses `GPU_TARGETS`
- **Test:** `tests/test_engine_bump.py::test_e6_gpu_targets_var_renamed`

### Requirement: E7 updates python/torch pins
When `requires-python` or a `torch==`/`torch>=` pin in pyproject/requirements
changes (e.g. `cu128` → `cu130`), the bump MUST update `toolchain.python` /
`torch_backend`.

#### Scenario: torch backend updated
- **Given** a fixture pyproject `torch==2.9.0+cu128` changing to `+cu130`
- **When** the bump derives
- **Then** `torch_backend` is updated for the engine
- **Test:** `tests/test_engine_bump.py::test_e7_torch_backend_updated`

### Requirement: E8 hard-fails on a removed launch flag
When a flag in the skill's `launch` is no longer accepted by the built cpu
image's `--help` (or is absent from `flags_from`), the bump MUST record a
hard-fail. The pin STILL moves and a PR is STILL created, with the hard-fail
flagged in the PR body so a human fixes the skill (CI goes red on the build).

#### Scenario: removed launch flag is flagged, PR still opens
- **Given** a built cpu image whose `--help` lacks a skill launch flag
- **When** the bump derives
- **Then** it records a hard-fail naming the flag, the pin still moves, and a PR
  is created whose body flags the hard-fail
- **Test:** `tests/test_engine_bump.py::test_e8_removed_launch_flag_hard_fails`

### Requirement: E9 reports per-backend watch diff
The bump MUST `git diff --numstat old..new -- <upstream_watch>` and map changed
files to backends (`ggml-cuda/` → cuda, `ggml-hip/` → rocm, `ggml-vulkan/` →
vulkan, `ggml-metal/` → metal, top-level CMake/docs → all, `arg.cpp`/`server/`
→ launch), overridable by an `upstream_watch_backends:` map. This is report-only.

#### Scenario: watch diff maps to backends
- **Given** a fixture where only `ggml/src/ggml-cuda/CMakeLists.txt` changed
- **When** the bump derives
- **Then** the report lists `cuda` only
- **Test:** `tests/test_engine_bump.py::test_e9_watch_diff_maps_backends`

### Requirement: unparseable extractor input hard-fails
If an extractor cannot parse its file (file moved, recipe has no `cmake` line,
ARG missing), the bump MUST record a hard-fail with the path and the grep
output. The pin still moves and a PR is still created, with the hard-fail
flagged in the PR body. Nothing is guessed.

#### Scenario: unparseable recipe is flagged, PR still opens
- **Given** a recipe Dockerfile with no `cmake` line
- **When** the bump derives
- **Then** it records a hard-fail naming the path, the pin still moves, and a PR
  is created whose body flags the hard-fail
- **Test:** `tests/test_engine_bump.py::test_unparseable_recipe_hard_fails`

### Requirement: regen guard
`make generate-engine-params` after a bump MUST change only
`containers/engines/params/<id>.json` and `containers/engines/dockerfiles/<id>/*`
for the bumped engine. A diff anywhere else (including another engine's params)
MUST fail the job.

#### Scenario: bump of A cannot change B's params
- **Given** a bump of engine A
- **When** params are regenerated
- **Then** a change to engine B's params fails the job
- **Test:** `tests/test_engine_bump.py::test_regen_guard_isolates_engine`

### Requirement: PR CI builds only the changed engines
On `pull_request`, `ci.yml` MUST build/test only the engines whose
`containers/engines/params/<id>.json` differs from the base branch. A push to
`main` MUST still run the full matrix.

#### Scenario: PR scopes the engine matrix
- **Given** a PR changing only `params/ollama.json`
- **When** the engine matrix is computed with `CHANGED=origin/main`
- **Then** engine-image jobs run for ollama × enabled arches only
- **Test:** `tests/test_engine_bump.py::test_changed_engines_scopes_matrix`

#### Scenario: push to main runs the full matrix
- **Given** a push to `main`
- **When** the engine matrix is computed
- **Then** all engines × enabled arches are built
- **Test:** `tests/test_engine_bump.py::test_changed_engines_full_on_main`

#### Scenario: no engine built is a skip, not a failure
- **Given** a PR whose params do not differ from the base
- **When** the engine matrix is computed
- **Then** it is one `engine: none` placeholder row (an empty include list fails the workflow before a job `if:` runs, and `matrix` is not a legal name in a job-level `if:`), and every step of `engine-image` / `engine-published-test` skips that row and builds nothing
- **Test:** `tests/test_engine_bump.py::test_changed_engines_scopes_matrix`

### Requirement: bump-daily runs end-to-end without pushing
`make engine-bump-daily [DRY=1]` MUST run plan → derive → apply → regen and,
with `DRY=1`, print the plan and findings without creating a branch or PR.

#### Scenario: dry run does not push
- **Given** `DRY=1`
- **When** `engine_bump.bump_daily` runs
- **Then** it prints the plan and findings and creates no branch/PR
- **Test:** `tests/test_engine_bump.py::test_bump_daily_dry_no_push`

### Requirement: apply writes derived params into the skill
`engine_bump.bump` MUST, after deriving, write the `auto` findings into the
skill's frontmatter (renames, mirrored recipe flags, toolchain, gpu-targets var,
torch backend) so the regenerated params that `make build-engine` reads carry the
new arguments. A hard-fail finding MUST NOT be applied (nothing is guessed).

#### Scenario: new args land in the params for every arch
- **Given** a skill with an empty `cmake_flags` and an upstream commit whose
  recipe adds `-DGGML_BACKEND_DL=ON`
- **When** the bump derives, applies, and regenerates
- **Then** the generated params JSON carries `-DGGML_BACKEND_DL=ON` for every arch
  the engine supports
- **Test:** `tests/test_engine_bump.py::test_full_bump_lands_new_flag_in_params`

#### Scenario: hard-fail applies nothing
- **Given** a derive hard-fail (removed option)
- **When** the bump applies
- **Then** the skill's flags are untouched
- **Test:** `tests/test_engine_bump.py::test_apply_hard_fail_applies_nothing`

### Requirement: workflow is gated to collaborators/owner/bot
`engine-bump.yml` MUST refuse to run when the triggering actor is not a
collaborator, the repo owner, or `github-actions[bot]`.

#### Scenario: non-collaborator is refused
- **Given** a workflow_dispatch by a non-collaborator
- **When** the guard job runs
- **Then** the run fails with an error and no bump job runs
- **Test:** CI job `guard` in `engine-bump.yml` (mirrors `ci.yml` guard)

### Requirement: engine bump runs on its own weekly cron, separate from the registry sync
The engine pin bump MUST run on a weekly cron schedule separate from the registry
sync (`registry-sync.yml`), so the two jobs run at different times and never
block each other.

#### Scenario: separate cron schedules
- **Given** `registry-sync.yml` on cron `17 5 * * *` (daily) and `engine-bump.yml`
  on cron `23 6 * * 1` (weekly, Monday)
- **When** the two workflows are scheduled
- **Then** they run at different times, independently
- **Test:** CI jobs `schedule` in `registry-sync.yml` and `engine-bump.yml`
