# engine-push-requires-binary

## ADDED Requirements

### Requirement: a push publishes only an image whose binary file accepts a flag
`make push-engine` MUST run the image version check before it tags or pushes.
That check MUST resolve the engine binary to a file inside the image and run
that file with the version/help flags the engine documents. A Python import MUST
NOT satisfy the check. The file MUST exist. One of those flags MUST exit 0.
`entrypoint.sh info` MUST still report port 11434 and model `llm-local`, and
`entrypoint.sh detect` MUST still print a version. When the check fails, or the
local image tag is missing, the push MUST return without running `docker tag` or
`docker push`. When the check passes, the push MUST publish the pinned tag and
the moving per-arch tag. The engine-image job MUST still run
`make test-engine-stage` before `make push-engine`. Neither the binary path nor
its flags MAY be added to the hashed params, so published image tags do not move.

### Requirement: every engine documents the flags its binary answers
Every servable engine skill MUST declare `binary_flags` (a subset of
`--version`, `--help`, `-h`) naming the flags its own binary answers, and
`make generate-engine-params` MUST write them, with the file each image must
contain, into `containers/engines/binaries.json`. That manifest MUST be
generated (never hand-edited), MUST cover every engine x variant in the frozen
params, MUST be checked for staleness by `make check-engine-params`, and MUST
NOT be part of the image-tag hash. A backend whose CLI initialises its device at
startup MAY be marked `binary_probe: device`; such a variant MUST still contain
the binary file, and its version MUST be proven by the image's `detect`.

#### Scenario: every published image names its binary file and its flags
- **Given** the CI matrix and the frozen params for every engine x variant
- **When** each one is looked up in `containers/engines/binaries.json`
- **Then** each entry names the file its image must contain
- **And** each entry names at least one documented version/help flag
- **Test:** `tests/test_engine_skills.py::test_every_published_image_has_a_binary_and_documented_flags`

#### Scenario: the manifest is generated and never moves a tag
- **Given** the current engine skills regenerated into a manifest
- **When** it is compared with the committed `binaries.json` and with the hashed inputs
- **Then** the committed manifest equals what the skills generate
- **And** the manifest is not one of the hashed inputs and the params carry no binary
- **Test:** `tests/test_engine_skills.py::test_the_manifest_is_generated_and_never_part_of_the_image_hash`

#### Scenario: an engine without documented flags fails validation
- **Given** a servable engine skill with `binary_flags` removed or misspelled
- **When** `make skills-validate` runs
- **Then** validation reports it
- **Test:** `tests/test_engine_skills.py::test_validator_requires_documented_binary_flags`

#### Scenario: a CLI that needs its device still has to ship the file
- **Given** a variant marked `binary_probe: device` (vllm cuda)
- **When** the probe finds the file but no flag answers, and when the file is missing
- **Then** the first passes (its version comes from `detect`) and the second fails
- **Test:** `tests/test_engine_skills.py::test_a_device_cli_is_exempted_only_where_the_file_still_has_to_be_there`

#### Scenario: a missing binary is not published
- **Given** a local engine image whose version check fails
- **When** `push` runs
- **Then** it returns failure
- **And** it does not tag or push the image
- **Test:** `tests/test_engine_skills.py::test_push_refuses_when_the_binary_does_not_report_a_version`

#### Scenario: a present binary is published after the check
- **Given** a local engine image whose version check passes
- **When** `push` runs
- **Then** the version check runs before any registry command
- **And** the pinned tag and the moving arch tag are pushed
- **Test:** `tests/test_engine_skills.py::test_push_publishes_only_after_the_binary_reports_a_version`

#### Scenario: a missing local image is not checked or published
- **Given** no local image for the tag
- **When** `push` runs
- **Then** it returns failure without the version check and without a registry command
- **Test:** `tests/test_engine_skills.py::test_push_does_not_publish_an_unbuilt_image`

#### Scenario: the latest published image's binary is probed for real
- **Given** an engine x arch already published to GHCR
- **When** `make test-published-engine` runs (the `engine-published-test` matrix)
- **Then** it pulls the latest published image (`pull_published`: no local build,
  digest matched to the moving `:<arch>` alias) and runs the same binary probe
  inside that exact image
- **And** the probe must pass (or, for a `probe: device` variant, the file must exist)
- **Test:** `tests/test_published_engine_binary.py::test_latest_published_image_binary_file_answers_its_documented_flags`

#### Scenario: a device variant still probes its documented flags
- **Given** a variant marked `binary_probe: device` (vllm cuda)
- **When** the probe runs
- **Then** the engine binary file is still run with its documented flags first
  (the exemption is a deliberate rc-2 tolerance, never a skipped probe), and a
  missing file (rc 1) still fails
- **Test:** `tests/test_engine_skills.py::test_device_variant_still_probes_its_documented_flags`

#### Scenario: a single-engine bump preserves the aggregate manifest
- **Given** a committed `containers/engines/binaries.json` with another engine's entry
- **When** `make generate-engine-params ENGINE=<id>` runs for one engine
- **Then** the other engine's manifest entry is kept verbatim and only the bumped
  engine's entry is updated
- **And** the regen scope guard accepts `containers/engines/binaries.json` as in-scope
- **Test:** `tests/test_engine_bump.py::test_regen_guard_accepts_the_aggregate_binaries_manifest`
