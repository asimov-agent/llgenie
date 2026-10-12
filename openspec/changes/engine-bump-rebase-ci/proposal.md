# engine-bump-rebase-ci

## Why

The engine-bump workflow (`.github/workflows/engine-bump.yml`, issue #107) opens
a `chore/engine-bump-<id>` PR per changed engine, but **nothing keeps those PRs
current with `main`**. Today the only thing that forward-merges `main` into a
behind engine-bump PR is the watch-loop dispatcher
(`scripts/watchloop_dispatch.py`), which runs as a **host crontab** (`*/20 * * * *`)
on the machine the repo is cloned into — not in CI. On a clone where `origin`
is the fork, the engine-bump branches (which live on the upstream
`asimov-agent/llgenie`) were rebased against a stale fork `main` and stalled at
the never-merge-behind gate (issue #9 / #206).

The rebasing of `chore/engine-bump-*` PRs must be a **pure CI job**: a GitHub
Actions cron that finds those open PRs and, when one is behind `main`,
forward-merges the latest `main` into it and pushes back — automatically, and
only when the merge applies cleanly. It must reuse the SAME sync logic the
dispatcher uses (no duplicated implementation, per AGENTS.md).

## What Changes

- **`scripts/engine_bump_sync.py`** — a small shared module holding the pure
  sync logic both callers use:
  - `is_engine_bump_pr(pr)` — head ref starts with `chore/engine-bump-` OR head
    repo `full_name == asimov-agent/llgenie`.
  - `upstream_remote(repo, run_git, log)` / `upstream_main(...)` — resolve the
    upstream remote by URL, add a named `upstream` remote when absent, fall back
    to `origin`.
  - `sync_pr_with_main(pr, repo, run_git, log)` — forward-merge the upstream
    `main` into a behind engine-bump PR branch and force-with-lease-push it
    back; returns True only when the merge applied cleanly.
- **`scripts/watchloop_dispatch.py`** — imports the shared functions from
  `engine_bump_sync` instead of defining its own copies (no duplication).
- **`scripts/engine_bump_rebase.py`** — the CI entrypoint: lists open
  `chore/engine-bump-*` PRs on `asimov-agent/llgenie` via the GitHub API, and
  for each one that is behind `main`, calls the shared `sync_pr_with_main`.
  `--dry` prints what it would do without pushing.
- **`.github/workflows/engine-bump-rebase.yml`** — a daily cron (plus
  `workflow_dispatch`) that checks out `main` with the owner PAT
  (`secrets.BUMP_TOKEN`, the same token `engine-bump.yml` uses) and runs
  `scripts/engine_bump_rebase.py`. Guarded like `engine-bump.yml` (only
  collaborators/bots/owners may trigger).

## User-Visible Impact

No change to user-facing serving/model commands. Engine-bump PRs stop stalling
at the never-merge-behind gate: a daily CI job keeps them rebased onto the
latest `main` without depending on the dev machine's crontab.

## Non-Goals

- No change to how engine-bump PRs are *created* (that stays in
  `engine-bump.yml`).
- No change to the watch-loop dispatcher's other duties (worker spawn, cleanup,
  repair) — only its engine-bump sync logic is shared out.
- The dispatcher's host crontab is left as-is; this adds a CI path, it does not
  remove the host path.
