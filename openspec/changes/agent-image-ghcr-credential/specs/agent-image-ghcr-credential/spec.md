# agent-image-ghcr-credential

## ADDED Requirements

### Requirement: the agent-image publish uses the credential this repo already publishes with

`publish-agent-image.yml` MUST log in to GHCR with `secrets.GITHUB_TOKEN` as `github.actor` — the same
credential and account `.github/workflows/ci.yml`'s `ci-images` job publishes `llgenie/test` and
`llgenie/openspec` with — and the job MUST declare `packages: write`. It MUST NOT log in with the owner PAT
(`secrets.BUMP_TOKEN`), which carries no `write:packages` and makes GHCR answer
`403 permission_denied: The token provided does not match expected scopes`.

WHEN the publish job authenticates to GHCR
THEN it does so with `secrets.GITHUB_TOKEN` as `github.actor` under `packages: write`, so the push the job
exists to perform is permitted.

#### Scenario: the login names the credential that can push

- **Given** the `publish` job of `publish-agent-image.yml`
- **When** its `docker login ghcr.io` step is read
- **Then** the secret it names is `GITHUB_TOKEN` and the user it logs in as is `github.actor`
- **And** the workflow declares `permissions: packages: write`
- **Test:** `tests/test_ci_images.py::test_the_agent_publish_logs_in_with_the_credential_its_push_check_proves`

### Requirement: the pre-flight proves the credential the login used

The push pre-flight (`make agent-image-push-check`, #335) MUST be handed the same credential the login step
names. A pre-flight run against a different secret than the login proves nothing about the push the job
will attempt, and that divergence is what let this job look configured while it could never publish.

WHEN the pre-flight step's `GHCR_TOKEN` and the login step's secret are compared
THEN they are the same secret, so the verdict the pre-flight prints is the push's own verdict.

#### Scenario: login secret and pre-flight secret are one

- **Given** the `publish` job's login step and its `make agent-image-push-check` step
- **When** each one's referenced secret is extracted
- **Then** the two names are identical, and equal `GITHUB_TOKEN`
- **Test:** `tests/test_ci_images.py::test_the_agent_publish_logs_in_with_the_credential_its_push_check_proves`

### Requirement: the workflow and README state the measured reason, not an organization theory

The workflow header, `scripts/ci_images.py pushcheck`'s missing-credential message and the `README.md`
paragraph MUST all name the credential the job logs in with and the measured refusal, so a maintainer is
not sent after a permission that does not exist (`asimov-agent` is a user account, so "Create organization
package" never applied) and the documentation cannot drift from the YAML.

WHEN the publish workflow's header, the push-check's message and the README paragraph are read
THEN each describes `secrets.GITHUB_TOKEN` with `packages: write`, and none still claims the owner PAT is
required.

#### Scenario: prose matches the YAML

- **Given** the workflow header, `scripts/ci_images.py pushcheck` and `README.md`
- **When** the credential each one names for the agent-image publish is read
- **Then** all three name `GITHUB_TOKEN` with `packages: write`, and the measured `403 permission_denied`
  refusal is the stated reason the owner PAT was dropped
- **Test:** the workflow half is
  `tests/test_ci_images.py::test_the_agent_publish_logs_in_with_the_credential_its_push_check_proves`; the
  prose half is read with the diff and `make check-docs` keeps the README paragraph in place.
