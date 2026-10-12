# watchloop-rebase-upstream-main — spec of record

Capabilities this change adds to the watch-loop dispatcher and AGENTS.md.

## ADDED Requirements

### Requirement: only engine-bump PRs are auto-rebased against upstream main

`sync_pr_with_main(pr)` MUST bring a behind PR's head up to date with `main` so
the never-merge-behind gate (issue #9) can re-attempt, and MUST use the
UPSTREAM `asimov-agent/main` — resolved from the clone's remote URLs, never
assumed from the name `origin` — as the merge source **only** when the PR is an
engine-bump PR (`chore/engine-bump-*` head ref, or a head repo whose
`full_name` is `asimov-agent/llgenie`). Every other PR MUST be synced against
`origin/main` exactly as before. A merge conflict MUST NOT be auto-resolved: the
branch is left for its worker and `False` is returned.

#### Scenario: engine-bump PR behind main on a fork-origin clone

- **WHEN** `sync_pr_with_main(pr)` runs for an engine-bump PR
  (`head.repo.full_name == "asimov-agent/llgenie"`, e.g.
  `chore/engine-bump-tensorfold`) on a clone whose `origin` is the fork
- **THEN** the loop fetches the branch from and merges the UPSTREAM
  `asimov-agent/main` (the remote resolved from its URL), then
  force-with-lease-pushes the synced branch back to that same upstream remote
- **AND** `origin/main` is never used as the merge source nor the push target
- **Test:** `tests/test_watchloop_dispatch.py::TestUpstreamMainResolution::test_sync_engine_bump_pr_merges_the_upstream_main`

#### Scenario: worker (fork) PR keeps the origin behaviour

- **WHEN** `sync_pr_with_main(pr)` runs for a non-engine-bump PR whose head
  repo is the fork (e.g. `feat/*`)
- **THEN** the loop merges `origin/main` and force-with-lease-pushes to `origin`
  exactly as before
- **AND** `upstream/main` is never the merge source for that PR
- **Test:** `tests/test_watchloop_dispatch.py::TestUpstreamMainResolution::test_sync_worker_pr_keeps_origin_behaviour`

#### Scenario: engine-bump PR classified by head ref prefix

- **WHEN** `is_engine_bump_pr(pr)` is called with a PR whose head ref starts
  with `chore/engine-bump-`
- **THEN** it returns `True`, even when the PR dict carries no `head.repo`
- **Test:** `tests/test_watchloop_dispatch.py::TestUpstreamMainResolution::test_is_engine_bump_pr_by_ref_prefix`

#### Scenario: non-engine-bump PR classified false

- **WHEN** `is_engine_bump_pr(pr)` is called with a PR whose head ref is
  `feat/x` and whose head repo is the fork
- **THEN** it returns `False`
- **Test:** `tests/test_watchloop_dispatch.py::TestUpstreamMainResolution::test_is_engine_bump_pr_by_head_repo`

### Requirement: upstream remote resolved from URL, added when absent

An engine-bump PR's sync target MUST be resolved by matching a clone's remote
URLs against `asimov-agent/llgenie`, never by trusting the name `origin`. When
no remote matches, the loop MUST add a remote named `upstream` pointing at
`https://github.com/asimov-agent/llgenie.git`; only when that add fails does it
fall back to `origin`.

#### Scenario: ssh-style upstream URL recognised

- **WHEN** a clone has only `origin` = `git@github.com:asimov-agent/llgenie.git`
- **THEN** `upstream_remote()` returns `"origin"`
- **Test:** `tests/test_watchloop_dispatch.py::TestUpstreamMainResolution::test_ssh_style_upstream_url_is_recognised`

#### Scenario: fork+upstream layout resolves `upstream`

- **WHEN** `git remote -v` lists the fork as `origin` and the upstream as
  `upstream`, in either order
- **THEN** `upstream_remote()` returns `"upstream"` and
  `upstream_main()` returns `"upstream/main"`
- **Test:** `tests/test_watchloop_dispatch.py::TestUpstreamMainResolution::test_upstream_remote_is_resolved_from_the_url_not_the_name`

#### Scenario: missing upstream remote is added

- **WHEN** a clone has only the fork as `origin`
- **THEN** `upstream_remote()` adds a remote named `upstream` pointing at the
  upstream URL and returns `"upstream"`
- **Test:** `tests/test_watchloop_dispatch.py::TestUpstreamMainResolution::test_missing_upstream_remote_is_added`

### Requirement: AGENTS.md mandates a closing-issue keyword on every PR body

AGENTS.md MUST state that a PR body always ends by referencing the issue it
closes as `closes #<issue id>` (the deliberate closing keyword the loop's
`process_merge_gate` / `issue_has_pr` already parse). This keeps every PR
traceable back to its issue (issue #206 requirement).

#### Scenario: PR body closes its issue

- **WHEN** a worker/agent opens a PR
- **THEN** AGENTS.md directs that its body end with `closes #<issue id>`

## MODIFIED Requirements

### Requirement: worker worktrees and cleanup stay on origin/main

The over-broad change that keyed EVERY watch-loop operation on the upstream main
is narrowed back: `ensure_worktree` (spawn + rebase), `_merged_into_main` / the
stale-worktree cleanup sweep, and the worker/repair prompts MUST all keep their
pre-existing `origin/main` behaviour, because worker branches live on the fork's
`origin`.

#### Scenario: worktree rebase stays on origin/main

- **WHEN** `ensure_worktree` rebases an existing worktree whose branch is behind
- **THEN** it rebases onto `origin/main`, not the upstream main
- **Test:** `tests/test_watchloop_dispatch.py::TestEnsureWorktreeSync::test_existing_worktree_behind_is_rebased`

#### Scenario: cleanup ancestry check stays on origin/main

- **WHEN** `_merged_into_main(branch)` runs the cleanup ancestry check
- **THEN** it compares against `origin/main`
- **Test:** `tests/test_watchloop_dispatch.py::TestUpstreamMainResolution::test_merged_into_main_compares_against_origin_main`

#### Scenario: worker and repair prompts rebase onto origin/main

- **WHEN** a worker or repair prompt is built
- **THEN** it instructs rebasing onto `origin/main` (never upstream/main)
- **Test:** `tests/test_watchloop_dispatch.py::TestUpstreamMainResolution::test_worker_prompt_rebases_onto_origin_main`
  and `...::test_repair_prompt_rebases_onto_origin_main`
