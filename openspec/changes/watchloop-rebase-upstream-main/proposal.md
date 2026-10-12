# watchloop-rebase-upstream-main

## Why

The watch-loop merge gate (`scripts/watchloop_dispatch.py`, host crontab every
20 min) forward-merges `main` into a behind open PR so the never-merge-behind
gate (issue #9) can re-attempt after CI re-runs. The merge source was the
literal `origin/main`. On the macOS clone `origin` IS the fork
(`andyholst/llgenie`), not the upstream `asimov-agent/llgenie`:

- The **engine-bump bot's PRs** (`chore/engine-bump-*`, opened by
  `.github/workflows/engine-bump.yml`, issue #107) have their branches pushed
  **directly to `asimov-agent/llgenie`** — the upstream — never to a fork. On a
  clone where `origin` is the fork those branches don't exist there, and
  rebasing them against a stale fork `main` sent them to the never-merge-behind
  gate forever.
- Worker PRs (`feat/*`) are pushed to the fork's `origin` and were already
  handled correctly against `origin/main`.

The fix is deliberately narrow: **only** the engine-bump bot's PRs are
auto-rebased/forward-merged against the UPSTREAM `asimov-agent/main`, resolved
from the clone's remotes by URL (never assumed from the name `origin`). Every
other watch-loop operation (worker worktree spawn/rebase, stale-worktree
cleanup, worker/repair prompts) stays keyed on `origin/main` as before.

## What Changes

- **`is_engine_bump_pr(pr)`** classifies a PR as an engine-bump PR when its head
  ref starts with `chore/engine-bump-` OR its head repo `full_name ==
  asimov-agent/llgenie`.
- **`sync_pr_with_main(pr)`** now resolves the sync remote per-PR: engine-bump
  PRs are fetched from, merged against, and force-with-lease-pushed back to the
  UPSTREAM remote's `main`; every other PR is synced against `origin/main`
  exactly as before.
- **`upstream_remote()` / `upstream_main()`** resolve the upstream remote from
  its URL (not its name), adding a named `upstream` remote when none exists and
  falling back to `origin` when it cannot be added. Used only by the engine-bump
  sync path.
- **OpenSpec + docs**: the change adds `proposal.md`/`spec.md`/`tasks.md` (the
  original PR carried only `.openspec.yaml`), and AGENTS.md gains the rule that
  every PR body must end with `closes #<issue id>`.

## User-Visible Impact

No change to user-facing serving/model commands. Fixes the watch loop's
engine-bump PRs stalling at the never-merge-behind gate on clones where
`origin` is the fork, without disturbing worker/cleanup behaviour.

## Non-Goals

- Worker `feat/*` branches are NOT rebased against upstream main (they live on
  the fork and keep the existing `origin/main` behaviour).
- No change to worktree spawning, stale-worktree cleanup, or worker/repair
  prompts beyond reverting them to their pre-existing `origin/main` behaviour.
