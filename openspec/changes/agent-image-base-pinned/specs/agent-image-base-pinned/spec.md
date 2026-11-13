# Spec Delta: agent-image-base-pinned

## ADDED Requirements

### Requirement: The agent image's base shall have no mutable default

`containers/agent/Dockerfile` SHALL declare `ARG TEST_IMAGE` with NO default value, and its
`FROM ${TEST_IMAGE}` SHALL resolve only to a ref supplied through `--build-arg`. Every wired
build path in `scripts/ci_images.py` (`ensure`, `_build_local`, `_buildx_push`) SHALL keep
passing the exact hashed test-image ref, and no Dockerfile on `main` SHALL carry a `FROM` that
can resolve to a `:latest` tag.

#### Scenario: bare build fails loudly

- **Given** `containers/agent/Dockerfile` at its committed state
- **When** `docker build -f containers/agent/Dockerfile .` runs with no `--build-arg TEST_IMAGE`
- **Then** the build exits non-zero with an empty-base error instead of resolving a mutable alias

#### Scenario: wired paths still pin the hashed ref

- **Given** a registry without the agent image's hash tag
- **When** `ci_images.py publish agent` runs
- **Then** the buildx build passes `--build-arg TEST_IMAGE=ghcr.io/asimov-agent/llgenie/test:<hash>`
  exactly as before

#### Scenario: the no-default shape is locked

- **Given** the repository test battery
- **When** `tests/test_ci_images.py::test_agent_dockerfile_has_no_latest_base_default` runs
- **Then** it asserts the Dockerfile's only `ARG TEST_IMAGE` line is the bare form and no
  pre-`FROM` block references `llgenie/test:latest`

#### Scenario: the scan sees no dockerfile latest-base

- **Given** merged `main` after this change lands
- **When** `make security-scan TOOL=trivy` reports misconfigurations
- **Then** no Dockerfile in the tree carries a `:latest`-base misconfig row
