# engine-bump-install-kind

## ADDED Requirements

### Requirement: a release archive replaces a pip install
When the new pin is a tag whose GitHub release publishes native archives
(`<name>-<version>-<os>-<arch>.tar.gz` with a sibling `.sha256`), and the
skill's install steps still fetch that engine with `uv`/`pip` from `git+`,
the bump MUST rewrite `install:` to a checksum-verified archive download and
unpack, one asset per backend. A release with no such assets MUST leave the
install steps unchanged. The detection MUST read the live release, not a
hardcoded engine table.

#### Scenario: pip install becomes a checksum-verified archive
- **Given** a skill whose `install.cuda` and `install.metal` are
  `uv pip install 'engine @ git+…@v{version}'`
- **And** the new tag's release lists `engine-<ver>-linux-x86_64.tar.gz`,
  `engine-<ver>-macos-arm64.tar.gz` and a `.sha256` beside each
- **When** the bump applies the release-archive finding
- **Then** both backends download their archive, check the sibling checksum,
  and unpack `bin/` into `{prefix}/{version}`
- **And** neither step still contains `git+` or `uv pip`
- **Test:** `tests/test_engine_bump.py::test_apply_release_archive_replaces_pip_install`

#### Scenario: derive reports the live release's archives
- **Given** the TensorFold skill pinned to tag `v1.0.5`
- **When** `derive` runs against that pin
- **Then** `auto.release_assets` lists the linux-x86_64 and macos-arm64 archives
- **And** a branch pin produces no `release_assets`
- **Test:** `tests/test_engine_bump.py::test_derive_reports_the_live_release_archives`

#### Scenario: the live TensorFold 1.0.5 release is detected as archives
- **Given** the published TensorFold v1.0.5 GitHub release
- **When** the bump lists its assets
- **Then** it reports a linux-x86_64 archive and a macos-arm64 archive, each
  with a sibling `.sha256`
- **Test:** `tests/test_engine_bump.py::test_tensorfold_v1_0_5_release_is_native_archives`

#### Scenario: the archive steps install the published binary
- **Given** the install steps E10 writes for TensorFold 1.0.5
- **When** they run against the published release archive
- **Then** the checksum passes and `bin/tensorfold-native --version` reports 1.0.5
- **And** the archive matches this host's machine (`x86_64` or `arm64`), not only its OS name
- **And** this test runs on the Linux unit job only (`make test-engine-bump-live`), not on macOS
- **Test:** `tests/test_engine_bump.py::test_tensorfold_release_archive_unpacks_and_runs`

#### Scenario: a wheel release is not rewritten
- **Given** a skill installed with `uv pip install`
- **And** the new tag's release lists only `.whl` assets
- **When** the bump applies
- **Then** the install steps are unchanged
- **Test:** `tests/test_engine_bump.py::test_apply_release_archive_ignores_wheels`

### Requirement: toolchain and GPU-target rewrites stay in their block
The toolchain rewrite MUST change only lines inside the `toolchain:` block.
The GPU-targets rename MUST change `AMDGPU_TARGETS` only inside `hw_flags:`
and in prose that names the old variable. `prereqs:` and
`derive.gpu_targets_var.candidates` MUST be byte-identical.

#### Scenario: prereqs and derive candidates survive a toolchain bump
- **Given** a skill with `prereqs.cuda: [nvcc]`, `prereqs.rocm: [hipconfig]`,
  `derive.gpu_targets_var.candidates: [GPU_TARGETS, AMDGPU_TARGETS]` and
  `hw_flags.rocm` using `AMDGPU_TARGETS`
- **When** the bump applies `toolchain.cuda=13.0.3` and
  `gpu_targets_var=GPU_TARGETS`
- **Then** `prereqs.cuda` is still `[nvcc]` and `prereqs.rocm` is still
  `[hipconfig]`
- **And** `candidates` still lists `AMDGPU_TARGETS`
- **And** `hw_flags.rocm` uses `GPU_TARGETS`
- **Test:** `tests/test_engine_bump.py::test_apply_toolchain_does_not_clobber_prereqs`

### Requirement: the bump unit suite is green inside make test-unit
`tests/test_engine_bump.py` is part of `make test-unit`. A fixture whose pin is
newer than every upstream tag MUST produce no bump row. A sha-only move (same
tag, new commit) MUST still rewrite a hardcoded tag literal in `tests/` and
`README.md`. The collaborator-guard assert MUST read the guard job, not the
workflow header. The real `llama.cpp` cpu image build MUST run only where the
container runtime answers, and MUST NOT be in the hermetic `make test-unit`
list. The unit job MUST check out with full history so
`matrix(changed=origin/main)` can tell an unchanged image tag from a missing ref.

#### Scenario: a pin newer than every tag is not a bump
- **Given** a tag-pinned skill at `v0.40.3` and an upstream whose highest stable tag is `v0.40.0`
- **When** `plan` runs
- **Then** that engine is not in the bump list
- **Test:** `tests/test_engine_bump.py::test_plan_tag_picks_highest_stable_same_shape`

#### Scenario: a sha-only move rewrites the tag literal
- **Given** a bump whose tag did not change and whose sha did
- **And** `tests/` hardcodes that tag and that sha
- **When** the bump rewrites pin asserts
- **Then** the tag literal and the sha both move, and another engine's pin does not
- **Test:** `tests/test_engine_bump.py::test_bump_rewrites_hardcoded_pin_asserts`

#### Scenario: the guard job keeps the default token
- **Given** `engine-bump.yml` and `registry-sync.yml`
- **When** the guard job is read
- **Then** that job uses `secrets.GITHUB_TOKEN` and not `secrets.BUMP_TOKEN`, and neither workflow merges a PR
- **Test:** `tests/test_engine_bump.py::test_guard_keeps_default_token`

#### Scenario: the unit job can see origin/main
- **Given** the unit job in `pipeline.yml`
- **When** it checks out
- **Then** the checkout fetches full history
- **Test:** `tests/test_engine_bump.py::test_unit_job_fetches_history`

#### Scenario: the hermetic unit list does not build an image
- **Given** the `test-unit` recipe
- **When** its pytest file list is read
- **Then** `tests/test_engine_bump.py` is in it and `tests/test_engine_bump_build.py` is not
- **Test:** `tests/test_engine_bump.py::test_unit_recipe_keeps_the_image_build_out`
