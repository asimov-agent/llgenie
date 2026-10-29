# agent-image-pull-latest

## ADDED Requirements

### Requirement: agent pulls fetch GHCR latest

`pull agent` and `ensure agent` MUST pull `ghcr.io/<registry>/llgenie/agent:latest` and tag it
`llgenie/agent:latest`. They MUST NOT pull the content-hash ref. A missing `:latest` tag fails
`pull` without a build, and `ensure` builds locally only then.

WHEN an agent image is pulled or ensured
THEN the registry ref is GHCR `:latest`.

#### Scenario: pull agent uses latest

- **Given** a registry that serves `ghcr.io/asimov-agent/llgenie/agent:latest`
- **When** `ci_images.py pull agent` runs
- **Then** the only pull is that `:latest` ref, retagged `llgenie/agent:latest`
- **Test:** `tests/test_ci_images.py::test_agent_pull_uses_latest`

#### Scenario: ensure agent uses latest

- **Given** a registry that serves `ghcr.io/asimov-agent/llgenie/agent:latest`
- **When** `ci_images.py ensure agent` runs
- **Then** it pulls that `:latest` ref and does not build
- **Test:** `tests/test_ci_images.py::test_agent_ensure_pulls_latest`

### Requirement: publish points latest at the agent hash

`publish agent` MUST tag GHCR `:latest` at the content hash. When the hash is new, the build
pushes the hash and `:latest` together. When the hash is already published, the build is skipped
and `buildx imagetools create` moves `:latest` onto that hash. Test and OpenSpec publishes MUST
stay hash-only.

WHEN the agent image is published
THEN GHCR `:latest` names the same manifest as the content hash, and a published hash is not rebuilt.

#### Scenario: a new agent hash is pushed with latest

- **Given** a registry without the agent hash
- **When** `ci_images.py publish agent` runs
- **Then** the build tags the content hash and `ghcr.io/asimov-agent/llgenie/agent:latest` and pushes
- **Test:** `tests/test_ci_images.py::test_publish_agent_pins_the_test_image_it_builds_from`

#### Scenario: an already published agent hash still moves latest

- **Given** a registry that already has the agent hash
- **When** `ci_images.py publish agent` runs
- **Then** nothing is built, and imagetools points `:latest` at that hash
- **Test:** `tests/test_ci_images.py::test_publish_agent_moves_latest_when_the_hash_is_already_published`

### Requirement: test and openspec pulls stay on the content hash

`pull test` and `pull openspec` MUST keep pulling the content-hash ref. `make ci-image-refs` MUST
keep printing those hashes. `make agent-image-ref` MUST print the agent `:latest` ref, which is
the ref fix-bot passes to `docker run` unless `AGENT_IMAGE` overrides it.

WHEN a test image is pulled
THEN the ref is the content hash, and the agent ref target prints `:latest`.

#### Scenario: the test image pull is still the hash

- **Given** a registry that has the test image's hash
- **When** `ci_images.py pull test` runs
- **Then** the pulled ref is `ghcr.io/asimov-agent/llgenie/test:` plus 12 hex
- **Test:** `tests/test_ci_images.py::test_ci_pull_tags_the_local_name`

#### Scenario: agent-image-ref prints latest

- **Given** the Makefile
- **When** `make -n agent-image-ref` runs
- **Then** the recipe is `python3 scripts/ci_images.py latest agent`
- **Test:** `tests/test_fix_loop.py::test_the_new_make_targets_run_the_exact_commands`
