# engine-bump-rebase-ci — spec of record

Capabilities this change adds: a shared engine-bump sync module, a CI entrypoint
that rebases open `chore/engine-bump-*` PRs onto the latest `main`, and a daily
GitHub Actions workflow that runs it.

## ADDED Requirements

### Requirement: shared engine-bump sync module

`scripts/engine_bump_sync.py` MUST expose the pure sync logic that both the
watch-loop dispatcher and the CI rebase entrypoint use, so there is exactly ONE
implementation of "forward-merge the upstream `main` into a behind engine-bump
PR branch and push it back" (AGENTS.md: no dual paths for the same resource).

#### Scenario: engine-bump PR classified by head ref prefix

- **WHEN** `is_engine_bump_pr(pr)` is called with a PR whose head ref starts
  with `chore/engine-bump-`
- **THEN** it returns `True`, even when the PR dict carries no `head.repo`
- **Test:** `tests/test_engine_bump_sync.py::test_is_engine_bump_pr_by_ref_prefix`

#### Scenario: non-engine-bump PR classified false

- **WHEN** `is_engine_bump_pr(pr)` is called with a PR whose head ref is
  `feat/x` and whose head repo is the fork
- **THEN** it returns `False`
- **Test:** `tests/test_engine_bump_sync.py::test_is_engine_bump_pr_by_head_repo`

#### Scenario: upstream remote resolved from URL, added when absent

- **WHEN** `upstream_remote(repo, run_git, log)` runs against a clone whose
  remotes include `asimov-agent/llgenie` under any name (or none, in which case
  a named `upstream` remote is added)
- **THEN** it returns the remote name whose URL matches the upstream slug, and
  `upstream_main(...)` returns `<that remote>/main`
- **Test:** `tests/test_engine_bump_sync.py::test_upstream_remote_resolution`

#### Scenario: sync forward-merges upstream main and pushes back

- **WHEN** `sync_pr_with_main(pr, repo, run_git, log)` runs for an engine-bump
  PR whose branch is behind the upstream `main`
- **THEN** it fetches the branch from the upstream remote, forward-merges the
  upstream `main` into it, and force-with-lease-pushes the synced branch back to
  that same upstream remote
- **AND** it returns `True` only when the merge applied cleanly (a conflict
  returns `False` and never force-pushes)
- **Test:** `tests/test_engine_bump_sync.py::test_sync_merges_upstream_main_and_pushes_back`

### Requirement: CI rebase entrypoint

`scripts/engine_bump_rebase.py` MUST list the open `chore/engine-bump-*` PRs on
`asimov-agent/llgenie` via the GitHub API and, for each one that is behind
`main`, call the shared `sync_pr_with_main`. `--dry` MUST print what it would do
without pushing.

#### Scenario: dry run reports without pushing

- **WHEN** `engine_bump_rebase.py --dry` runs with open engine-bump PRs
- **THEN** it prints each behind PR it would rebase and performs no push
- **Test:** `tests/test_engine_bump_rebase.py::test_dry_run_reports_without_pushing`

#### Scenario: behind engine-bump PR is rebased

- **WHEN** `engine_bump_rebase.py` runs and an open `chore/engine-bump-*` PR is
  behind `main`
- **THEN** it calls the shared `sync_pr_with_main` for that PR
- **Test:** `tests/test_engine_bump_rebase.py::test_behind_engine_bump_pr_is_rebased`

### Requirement: daily CI workflow

`.github/workflows/engine-bump-rebase.yml` MUST run on a daily cron (and
`workflow_dispatch`), check out `main` with the owner PAT
(`secrets.BUMP_TOKEN`), and run `scripts/engine_bump_rebase.py`. It MUST be
guarded so only collaborators, bots, and owners may trigger it (same guard as
`engine-bump.yml`).

#### Scenario: workflow runs the rebase entrypoint

- **WHEN** the workflow fires (schedule or dispatch)
- **THEN** it checks out `main` with `secrets.BUMP_TOKEN` and runs
  `python3 scripts/engine_bump_rebase.py`
- **Test:** `tests/test_engine_bump_rebase.py::test_workflow_runs_the_rebase_entrypoint`
  (asserts the workflow YAML contains the cron, the BUMP_TOKEN checkout, and the
  entrypoint invocation)

## MODIFIED Requirements

### Requirement: dispatcher reuses the shared module

`scripts/watchloop_dispatch.py` MUST import `is_engine_bump_pr`,
`upstream_remote`, `upstream_main`, and `sync_pr_with_main` from
`engine_bump_sync` instead of defining its own copies, so the CI job and the
dispatcher share one implementation.

#### Scenario: dispatcher imports the shared sync functions

- **WHEN** `scripts/watchloop_dispatch.py` is imported
- **THEN** its `sync_pr_with_main` / `is_engine_bump_pr` / `upstream_remote` /
  `upstream_main` resolve to the shared `engine_bump_sync` implementations
- **Test:** `tests/test_watchloop_dispatch.py::TestUpstreamMainResolution::test_dispatcher_uses_shared_sync_module`
