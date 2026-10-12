# fix-engine-bump-rebase-guard

## ADDED Requirements

### Requirement: the rebase guard authenticates with the default token
`engine-bump-rebase.yml` MUST send `Authorization: Bearer $TOKEN` on the
collaborators request. `TOKEN` MUST be `${{ secrets.GITHUB_TOKEN }}`. The
header MUST NOT be the literal `Bearer ***`. `ci.yml`, `engine-bump.yml`,
and `registry-sync.yml` MUST use that same header. Checkout, push, and the
rebase command MUST keep using `secrets.BUMP_TOKEN`.

WHEN the guard calls `https://api.github.com/repos/${{ github.repository }}/collaborators/$ACTOR`,
THEN the request header is `Authorization: Bearer $TOKEN` and `TOKEN` is `secrets.GITHUB_TOKEN`.

#### Scenario: a collaborator dispatch is not refused by a literal header
- **Given** `engine-bump-rebase.yml` sets `TOKEN` to `${{ secrets.GITHUB_TOKEN }}`
- **When** the guard calls the collaborators endpoint
- **Then** the header is `Authorization: Bearer $TOKEN`
- **And** the run script does not contain `Bearer ***`
- **Test:** `tests/test_engine_bump_rebase.py::TestWorkflowYaml::test_guard_sends_the_token_variable`

#### Scenario: the other guards use the same header
- **Given** `ci.yml`, `engine-bump.yml`, and `registry-sync.yml`
- **When** each guard job is read
- **Then** each sends `Authorization: Bearer $TOKEN` from `secrets.GITHUB_TOKEN`
- **And** none of those files contain `Bearer ***`
- **Test:** `tests/test_engine_bump_rebase.py::TestWorkflowYaml::test_guard_sends_the_token_variable`
