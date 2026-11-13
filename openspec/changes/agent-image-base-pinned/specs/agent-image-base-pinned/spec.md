# Spec: the agent Dockerfile's TEST_IMAGE base has no mutable default

## MODIFIED Requirements

### Requirement: `ARG TEST_IMAGE` carries no value in `containers/agent/Dockerfile`

`containers/agent/Dockerfile` must declare the test-image base as `ARG TEST_IMAGE` with NO inline
default (no `=` value on the ARG line). `FROM ${TEST_IMAGE}` then resolves the base from the
build-arg only; a build that omits `--build-arg TEST_IMAGE=` fails loudly with an empty base name
instead of silently resolving to the mutable `:latest` alias. The comment above the ARG states the
arg is mandatory and that every wired builder passes the hashed ref.

#### Scenario: the Dockerfile pins no mutable test-image tag

- **Test:** `tests/test_ci_images.py::test_agent_dockerfile_test_image_arg_has_no_default`

Given a reader loads `containers/agent/Dockerfile`
When they read the line that enters the test-image base
Then it is `ARG TEST_IMAGE` with no value
And no `:latest` tag appears on the ARG (the text-lock test asserts this)

#### Scenario: the bare build without the build-arg fails loudly

- **Test:** CI `security-scan` job -> `make security-scan TOOL=trivy` (zero misconfig rows); bare
  `docker build -f containers/agent/Dockerfile .` replayable rc recorded in the PR body

Given a build context with `containers/agent/Dockerfile` as its Dockerfile and no
`--build-arg TEST_IMAGE`
When the image is built
Then it fails with an empty-base-name error and never references a mutable `:latest` tag. Proven
live by the acceptance criterion's replayable command: `docker build -f
containers/agent/Dockerfile .` exits non-zero with the empty-base error when run with the agent's
build args minus `TEST_IMAGE`.

## ADDED Requirements

### Requirement: a text lock pins that the agent Dockerfile's TEST_IMAGE ARG has no default

`tests/test_ci_images.py` MUST lock the Dockerfile's `ARG TEST_IMAGE` line to carry no default,
next to the existing lock that the publish build passes the hashed `--build-arg`. A change that
re-adds a `:latest` default reds this test.

#### Scenario: a re-added default reds the lock

- **Test:** `tests/test_ci_images.py::test_agent_dockerfile_test_image_arg_has_no_default`

Given the Dockerfile's `ARG TEST_IMAGE` line has no value
When `tests/test_ci_images.py` runs the new lock test
Then it asserts the ARG line carries no `=` default and no `:latest` tag
And the whole test battery passes in CI

### Requirement: every wired build path still passes the hashed TEST_IMAGE ref

`scripts/ci_images.py::build_args` continues to return `--build-arg TEST_IMAGE=<ghcr hashed ref>`
for agent builds (`ensure`, `_build_local`, `_buildx_push`), so `make agent-image`,
`make agent-image-pull`, `make publish-agent-image` and all CI legs build exactly as before —
unchanged by this change.

#### Scenario: the publish build still pins the hashed test-image ref

- **Test:** `tests/test_ci_images.py::test_publish_agent_pins_the_test_image_it_builds_from`

Given `scripts/ci_images.py publish agent` runs with an unpinned registry
When the build command is issued
Then it passes `--build-arg TEST_IMAGE=ghcr.io/asimov-agent/llgenie/test:<hash>` (locked by the
existing `test_publish_agent_pins_the_test_image_it_builds_from`)
And no local `:latest`-based agent build exists in the wired path
