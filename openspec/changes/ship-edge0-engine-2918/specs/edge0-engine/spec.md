# edge0-engine

## ADDED Requirements

### Requirement: the edge0 engine ships as a pack-format skill with the EDGE0.md v5 part wiring

A `skills/engines/edge0/SKILL.md` MUST exist, declare `servable: true`, `backends: [cuda]`,
`formats: [pack]`, and top-level `model_contract: "pack"` plus a `pack` block whose `parts` list
declares exactly the EDGE0.md v5 pack-directory parts (`model-skeleton.gguf`, `ple-fp8.gguf`,
`profile.bin`, `experts.bin`, `labels.bin`, `dense.bin`, `mtp`, `tokenizer`) and whose
`config_env` maps each pack-relative path to its env var (`STRATA_LATENT_A=experts.bin`,
`STRATA_LATENT_LABELS=labels.bin`, `STRATA_LATENT_DENSE=dense.bin`). The launch (`pre_launch` +
`launch`) MUST build its server config from the shipped v5 template
(`edge0-strata/edge0/models/edge0-145b.json`) with `{model}` as the pack directory, and the
install MUST follow EDGE0.md v5's Linux CUDA build (CMake+Ninja, `CMAKE_CUDA_COMPILER` =
`$(command -v nvcc)`, `CMAKE_CUDA_ARCHITECTURES` = the cuda arch list, `STRATA_ENABLE_CUDA=ON`,
`STRATA_GGML_DIR` — the pinned llama.cpp snapshot `3cf03257f…` unpacked into
`third_party/llama.cpp` — then `cmake --build build --target strata`; server venv via
`python3 -m venv` + `requirements.txt`).

WHEN the edge0 skill is read by `scripts/engine_skills.py`
THEN it validates clean AND declares `model_contract: "pack"` with the exact EDGE0.md v5
`pack.parts`/`pack.config_env` AND its v5 template placeholders survive the repo renderer as
literals for the runtime substitution.

#### Scenario: the skill declares the exact v5 pack parts and config_env

- **Given** the edge0 skill front matter
- **When** its `model_contract` and `pack` block are read
- **Then** `model_contract` is `"pack"` and `pack.parts` equals the EDGE0.md v5 ordered list
  (`model-skeleton.gguf`, `ple-fp8.gguf`, `profile.bin`, `experts.bin`, `labels.bin`, `dense.bin`,
  `mtp`, `tokenizer`)
- **And** `pack.config_env` is `STRATA_LATENT_A` → `experts.bin`, `STRATA_LATENT_LABELS` →
  `labels.bin`, `STRATA_LATENT_DENSE` → `dense.bin`
- **Test:** `tests/test_engine_edge0.py::test_edge0_skill_declares_the_pack_contract`

#### Scenario: the launch substitutes the shipped v5 template, placeholders intact

- **Given** the plan-rendered edge0 `pre_launch` and `launch`
- **When** they are read
- **Then** they name `edge0/models/edge0-145b.json` (the v5 server-config template)
- **And** the `${MODEL_DIR}`, `${PLE_IO}`, `${DU_FILE}`, `${LAT_FUSED_Q3K}` placeholders remain
  as literals (a `_render` brace-collision would have eaten them)
- **Test:** `tests/test_engine_edge0.py::test_edge0_v5_launch_substitutes_the_pack_template`

### Requirement: the edge0 Dockerfile lane and build-matrix cell exist on a CUDA-13 base

`make generate-engine-params ENGINE=edge0` MUST produce `containers/engines/params/edge0.json`
with a `cuda` variant whose `base` is a CUDA-13 devel image and whose `arch` is the fat consumer
arch list, and `containers/engines/dockerfiles/edge0/Dockerfile.cuda`. `scripts/engine_image.py`
`matrix(ci=True)` MUST include the `edge0`/`cuda` cell with `test` `detect` (the image's own
version test — a pack has no tiny smoke model) and `smoke` false. The generated params MUST match
what `make check-engine-params` regenerates (no drift).

WHEN `make generate-engine-params ENGINE=edge0` runs and the params are committed
THEN `make check-engine-params` reports 0 stale files AND the CI matrix resolves exactly one
`edge0` `cuda` cell (`smoke: false`, `test: detect`).

#### Scenario: the CUDA-13 base and arch list are frozen in the params

- **Given** the committed `containers/engines/params/edge0.json`
- **When** its `cuda` variant is read
- **Then** `base` starts with `nvidia/cuda:13` (`devel-ubuntu24.04`)
- **And** `arch` equals the fat consumer arch list and `detect` runs
  `…/build/strata --version`
- **Test:** `tests/test_engine_edge0.py::test_edge0_cuda_variant_builds_on_a_cuda13_base`

#### Scenario: the engine enters the CI build matrix

- **Given** `scripts/engine_image.matrix(ci=True)` over the committed params
- **When** the `edge0` rows are resolved
- **Then** exactly one row exists — `(cuda, smoke: false, test: detect, chat: "")`
- **Test:** `tests/test_engine_edge0.py::test_edge0_is_in_the_ci_build_matrix`

### Requirement: the edge0 deferral closes on a shipped skill

`data/unsupported-engines.json` MUST no longer carry an `edge0` entry, and
`make render-engine-skill-gap` + `make check-engine-skill-gap` MUST be green with `edge0` reported
`shipped` (image `true`, variants `[cuda]`, never-offered empty of `edge0-145b`).

WHEN the edge0 skill ships and the decision is removed
THEN `make check-engine-skill-gap` exits 0 AND the gap view marks `edge0` `shipped` with the
`cuda` image AND `edge0` has no `data/unsupported-engines.json` decision AND
`edge0-145b` is not in the never-offered set.

#### Scenario: a shipped skill replaces the dated deferral

- **Given** the shipped edge0 skill and the regenerated decisions/gap files
- **When** `data/unsupported-engines.json` and `engine_skill_gap.json` are read
- **Then** `edge0` is absent from the decisions and present in the shipped list with
  `image: true`
- **Test:** `tests/test_engine_edge0.py::test_edge0_is_shipped_not_deferred`
  (asserts the decision is gone); the full gate is `make check-engine-skill-gap`
