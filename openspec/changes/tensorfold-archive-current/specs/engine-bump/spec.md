# engine-bump

## ADDED Requirements

### Requirement: a release-archive install tracks {prefix}/current so the native state can be outdated

When the bump rewrites a pip install to a release-archive install, the derived steps MUST
unpack into `{prefix}/{version}` AND point `{prefix}/current` at that release
(`ln -sfn {prefix}/{version} {prefix}/current` as the LAST install step), and the skill MUST
set `binary: "{prefix}/current/bin/{id}"` with `detect: "{binary} --version"`. Because the
binary path no longer carries the pinned version, `detect` asks the INSTALLED binary its
version, so `native_status` can report `outdated` (an older release installed) and `current`
truthfully, not only `missing` / `current`.

WHEN the release-archive derivation runs
THEN the last install step links `{prefix}/current` to `{prefix}/{version}`, and the binary
is `{prefix}/current/bin/{id}`.

#### Scenario: the derived skill points the binary through {prefix}/current

- **Given** a skill that pip-installs the engine from git, and a release whose assets are
  checksummed native archives
- **When** the bump applies that release
- **Then** the last install step is `ln -sfn {prefix}/{version} {prefix}/current`
- **And** `binary` is `{prefix}/current/bin/{id}` and `detect` is `{binary} --version`
- **And** the `exe=$(find …)` link step still links the unpacked executable to `{id}`
- **Test:** `tests/test_engine_bump.py::test_apply_release_archive_replaces_pip_install`

#### Scenario: a full bump lands the current link and binary

- **Given** a git+ skill on `v9.1.0` and archives in the `v9.2.0` release file
- **When** the bump runs
- **Then** the rewritten skill's binary is `{prefix}/current/bin/{id}` and its last install
  step is the `{prefix}/current` link
- **Test:** `tests/test_engine_bump.py::test_bump_reads_the_destination_release`

### Requirement: the derived skill documents the --version flag its binary answers

The release-archive binary answers `--version` (the detect and `native_status` ask it), so the
derivation MUST ensure `--version` is among the documented `binary_flags`. When the pip-era
skill already documented `--help`, the block MUST become `["--help", "--version"]`; otherwise
`["--version"]`. The flags the skill's own detect uses MUST be a subset of the documented
flags (the `test_each_engine_documents_the_flags_its_binary_answers` contract).

WHEN the release-archive derivation rewrites a skill whose `binary_flags` is `["--help"]`
THEN the block becomes `["--help", "--version"]`.

#### Scenario: --version joins the documented flags

- **Given** a pip-installed skill whose `binary_flags` is `["--help"]`
- **When** the bump applies a release-archive release
- **Then** the rewritten skill's `binary_flags` is `["--help", "--version"]`
- **And** a skill with no `binary_flags` gets `["--version"]`
- **Test:** `tests/test_engine_bump.py::test_apply_release_archive_replaces_pip_install`

### Requirement: the seamless TensorFold tests drive whatever install the skill declares

`tests/test_tensorfold_seamless.py` MUST reach `missing` / `outdated` / `current` through the
REAL `engine_skills.native_status` and `install_engine_launchers.ensure_native` for BOTH the
pip/`uv tool install` skill (main today) and the release-archive skill (the `v1.1.1` bump),
and the picker labels (`(installs X on pick)` / `(installed A -> updates to X on pick)` /
`(installed X)`) MUST hold for both. The product code MUST NOT be mocked; only the external
tools the skill shells out to (`uv`, `curl`, `shasum`, `tar`, `tensorfold`) are real stand-in
executables on PATH that log their calls and materialise a plausible install. No test may be
skipped.

WHEN the seamless tests run against a pip/uv skill and against a release-archive skill
THEN both reach the three native states and the picker labels through the real product code.

#### Scenario: native_status is missing / outdated / current for both install kinds

- **Given** TensorFold absent, at an older release, or at the pinned release, under the live
  skill and under a release-archive skill
- **When** its native state is read through the skill's real detect
- **Then** it is `missing` / `outdated` / `current` with the installed and wanted versions
- **Test:** `tests/test_tensorfold_seamless.py::test_native_status_missing_outdated_current`

#### Scenario: ensure_native installs, updates and reuses for both install kinds

- **Given** a Mac without TensorFold, or with an older / the pinned release, under both kinds
- **When** llgenie ensures TensorFold
- **Then** it installs / updates / reuses with the skill's declared steps, and the start
  script is written
- **Test:** `tests/test_tensorfold_seamless.py::test_missing_tensorfold_is_installed_with_its_skill_install_script`,
  `tests/test_tensorfold_seamless.py::test_outdated_tensorfold_is_updated_to_the_pinned_release`,
  `tests/test_tensorfold_seamless.py::test_current_tensorfold_is_reused_without_reinstalling`

#### Scenario: the picker labels hold for the archive kind

- **Given** TensorFold absent / outdated / current under a release-archive skill
- **When** its native state is read the way the picker shows it
- **Then** the label says install / update / reuse, exactly like the pip kind
- **Test:** `tests/test_tensorfold_seamless.py::test_archive_kind_picker_labels`

### Requirement: the TensorFold image test asserts invariants, not a hardcoded install list

`tests/test_mac_trend_pick.py::test_tensorfold_image_is_cuda_only_and_built_by_linux_ci` MUST
assert the real invariants: the metal install is non-empty and is exactly the skill's declared
steps, it never uses `sudo`, it never pipes `curl` into `sh`/`bash`, the image is cuda-only,
and CI builds it on Linux. It MUST NOT hardcode the pip/`uv` install list.

WHEN the TensorFold image test runs
THEN it asserts the invariants, whatever install kind the skill declares.

#### Scenario: the image test is install-kind agnostic

- **Given** the generated TensorFold params and its declared native install
- **When** the CI matrix is computed
- **Then** the only image is cuda and CI builds it; metal is a native install that is
  non-empty, is the skill's declared steps, never elevates, and never pipes `curl` to a shell
- **Test:** `tests/test_mac_trend_pick.py::test_tensorfold_image_is_cuda_only_and_built_by_linux_ci`

### Requirement: the derived skill drops a pip prerequisite its steps no longer call

The release-archive derivation MUST remove `uv`/`pip`/`pip3` from the skill's `prereqs` when no
derived step names it, keeping every other documented tool and every backend entry. A leftover pip
prerequisite is a false precondition: `engine_skills.check(mode="native")` refuses the engine with
`missing prerequisite: uv` on a host that has no uv, for an install that never invokes it.

WHEN the release-archive derivation runs
THEN each `prereqs` flow list inside the block keeps only the tools its backends' steps still call.

#### Scenario: the pip tool leaves prereqs, the tools the steps call stay

- **Given** a skill whose `prereqs` name `uv` (common and cuda) and `curl`/`nvidia-smi`
- **When** the bump applies a release whose archives the steps download with `curl`
- **Then** `prereqs.common` no longer names `uv`
- **And** the backend entry keeps `curl` and `nvidia-smi`
- **Test:** `tests/test_engine_bump.py::test_apply_release_archive_replaces_pip_install`

#### Scenario: no uv required for the archive install, and the pip kind still demands one

- **Given** a Mac whose PATH has the skill's external tools but no `uv`
- **When** llgenie ensures TensorFold for the pick
- **Then** the release-archive kind installs and reaches the pinned release
- **And** the pip kind is still refused with `missing prerequisite: uv`
- **Test:** `tests/test_tensorfold_seamless.py::test_a_host_without_uv_only_blocks_the_pip_install`
