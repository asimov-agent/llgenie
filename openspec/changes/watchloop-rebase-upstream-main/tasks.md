# watchloop-rebase-upstream-main

## Dispatcher (engine-bump PRs rebased against upstream main)

- [x] 1.1 Add `is_engine_bump_pr(pr)` classifying a PR by `chore/engine-bump-`
      head-ref prefix OR head repo `full_name == asimov-agent/llgenie`.
- [x] 1.2 Narrow `sync_pr_with_main(pr)` so ONLY engine-bump PRs are fetched
      from, merged against, and force-with-lease-pushed back to the UPSTREAM
      remote + `asimov-agent/main`; all other PRs keep the `origin/main`
      behaviour.
- [x] 1.3 Add `upstream_remote()`/`upstream_main()` resolving the upstream
      remote from its URL, adding a named `upstream` remote when absent, and
      falling back to `origin` when the add fails.

## Revert the previous over-broad change

- [x] 2.1 Revert `ensure_worktree` to rebase/spawn against `origin/main`.
- [x] 2.2 Revert `_merged_into_main` and the stale-worktree cleanup sweep to
      compare against `origin/main`.
- [x] 2.3 Revert `worker_prompt` and `repair_prompt` to rebase instructions
      against `origin/main`.

## AGENTS.md + docs

- [x] 3.1 AGENTS.md gains: every PR body must end with `closes #<issue id>`.
- [x] 3.2 Write this change's `proposal.md` + `specs/watchloop/spec.md` +
      `tasks.md` (the prior PR carried only `.openspec.yaml`).

## Tests

- [x] 4.1 `sync_pr_with_main` engine-bump PR merges/pushes the upstream main.
- [x] 4.2 `sync_pr_with_main` non-bump PR keeps origin behaviour.
- [x] 4.3 `is_engine_bump_pr` by ref prefix and by head repo.
- [x] 4.4 upstream remote resolution (URL/ssh/added/fallback).
- [x] 4.5 worktree rebase, cleanup ancestry, and prompts stay on origin/main.
- [x] 4.6 `make test-unit` green (97 dispatcher tests incl. the new engine-bump
      cases).

## Verification

- [x] 5.1 `make openspec-validate NAME=watchloop-rebase-upstream-main` exit 0.
- [x] 5.2 `make lint` clean (all tracked files end with a newline).
- [x] 5.3 Updates pushed to the upstream PR branch; issue #206 + PR #207 bodies
      aligned with the narrowed scope.
