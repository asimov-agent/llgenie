# fix-bump-token-pr — spec

## ADDED Requirements

### Requirement: bump and sync PRs are opened with the owner PAT
`engine-bump.yml` and `registry-sync.yml` MUST check out, push and open or
update their PR with the repo secret `BUMP_TOKEN`, not `secrets.GITHUB_TOKEN`.
A PR authored by `github-actions[bot]` holds every `pull_request` workflow for
manual approval, and a push made with `GITHUB_TOKEN` starts no workflows. The
commit MUST be authored as the token owner. The collaborator guard MUST keep
using `secrets.GITHUB_TOKEN`. The workflows MUST NOT merge.

#### Scenario: the bump job uses the owner PAT
- **Given** `engine-bump.yml`
- **When** the bump job checks out, pushes and opens the PR
- **Then** those three steps use `secrets.BUMP_TOKEN` and the commit author is not `github-actions[bot]`
- **Test:** `tests/test_engine_bump.py::test_bump_pr_uses_owner_pat`

#### Scenario: the sync job uses the owner PAT
- **Given** `registry-sync.yml`
- **When** the sync job checks out, pushes and opens the PR
- **Then** those three steps use `secrets.BUMP_TOKEN` and the commit author is not `github-actions[bot]`
- **Test:** `tests/test_engine_bump.py::test_sync_pr_uses_owner_pat`

#### Scenario: the guard keeps the default token
- **Given** either workflow
- **When** the guard job checks the actor
- **Then** it uses `secrets.GITHUB_TOKEN` and neither workflow merges a PR
- **Test:** `tests/test_engine_bump.py::test_guard_keeps_default_token`
