# forward-github-token

## ADDED Requirements

### Requirement: test containers receive the GitHub token
Every workflow that exports `HF_TOKEN` MUST also export `GITHUB_TOKEN` from
`secrets.GITHUB_TOKEN`. On Linux, the test container (`TEST_OPTS`) and the
engine-test container (`ENGINE_TEST_ARGS`) MUST forward `GITHUB_TOKEN` and
`GH_TOKEN` by name, the same way they forward `HF_TOKEN`. The value MUST stay
in the environment and MUST NOT appear on the container command line.

#### Scenario: workflows export the Actions token
- **Given** `ci.yml`, `pipeline.yml`, `published.yml`, `engine-bump.yml`, and `registry-sync.yml`
- **When** their workflow `env` is read
- **Then** each sets `GITHUB_TOKEN` to `${{ secrets.GITHUB_TOKEN }}`
- **Test:** `tests/test_engine_bump.py::test_workflows_export_the_github_token`

#### Scenario: Linux containers forward the token by name
- **Given** the Linux `TEST_OPTS` and `ENGINE_TEST_ARGS` runners
- **When** their container environment flags are read
- **Then** each contains `-e GITHUB_TOKEN` and `-e GH_TOKEN`
- **And** neither assigns `GITHUB_TOKEN=` or `GH_TOKEN=` on that command
- **Test:** `tests/test_engine_bump.py::test_linux_test_containers_forward_the_github_token`

### Requirement: the release lookup sends the forwarded token
`_release_assets` MUST send `Authorization: Bearer` with the first non-empty
of `GITHUB_TOKEN` and `GH_TOKEN`. With no token it MUST send no
`Authorization` header. A 401 or 403 on the authenticated call MUST be retried
once with no `Authorization` header. Any other failure, including a 404, MUST
return no assets and MUST NOT be retried.

#### Scenario: the lookup sends GITHUB_TOKEN
- **Given** `GITHUB_TOKEN` is set and `GH_TOKEN` is also set
- **When** the release lookup runs
- **Then** the request's `Authorization` header is `Bearer` plus `GITHUB_TOKEN`
- **Test:** `tests/test_engine_bump.py::test_release_lookup_sends_the_github_token`

#### Scenario: GH_TOKEN is used when GITHUB_TOKEN is empty
- **Given** `GITHUB_TOKEN` is unset and `GH_TOKEN` is set
- **When** the release lookup runs
- **Then** the request's `Authorization` header is `Bearer` plus `GH_TOKEN`
- **Test:** `tests/test_engine_bump.py::test_release_lookup_uses_gh_token_when_github_token_is_empty`

#### Scenario: no token sends no Authorization header
- **Given** neither `GITHUB_TOKEN` nor `GH_TOKEN` is set
- **When** the release lookup runs
- **Then** the request has no `Authorization` header
- **Test:** `tests/test_engine_bump.py::test_release_lookup_without_a_token_sends_no_authorization`

#### Scenario: a foreign-repo denial is retried without the token
- **Given** `GITHUB_TOKEN` is set
- **And** the authenticated release request is denied with 403
- **When** the release lookup runs
- **Then** it requests the same release once more with no `Authorization` header
- **And** the assets from that second response are returned
- **Test:** `tests/test_engine_bump.py::test_release_lookup_retries_a_foreign_repo_denial_without_the_token`

#### Scenario: a missing release is not retried
- **Given** `GITHUB_TOKEN` is set
- **And** the release request answers 404
- **When** the release lookup runs
- **Then** it returns no assets
- **And** it does not send a second request
- **Test:** `tests/test_engine_bump.py::test_release_lookup_does_not_retry_a_missing_release`
