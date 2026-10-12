# remove-watchloop-crontab

## Why

The watch-loop dispatcher (`scripts/watchloop_dispatch.py`) runs as a **host
crontab** (`*/20 * * * *`, installed by `make cron-install`) on the machine the
repo is cloned into. It drives autonomous issue-working: a merge gate, an issue
spawner that launches Hermes workers, stuck-PR repair, and stale-worktree
cleanup. This is not wanted: the repo should not depend on a dev machine's
crontab, and autonomous issue-working is out of scope.

The ONLY watch-loop duty worth keeping is rebasing the open `chore/engine-bump-*`
PRs onto the latest `main` — and that is already a pure CI job
(`.github/workflows/engine-bump-rebase.yml`, issue #208) that reuses the shared
`scripts/engine_bump_sync.py`. So the host crontab and the rest of the
dispatcher are removed entirely.

## What Changes

- **Remove the host crontab plumbing:** `scripts/install_watchloop_cron.py`,
  the `cron-install` / `cron-uninstall` / `cron-snapshot` make targets, and the
  `ci-cron` CI job.
- **Remove the dispatcher:** `scripts/watchloop_dispatch.py`,
  `scripts/watch_report.py`, `scripts/serialized-make.py`,
  `scripts/worker-model.template`, and the `watch-report` / `ci-watch-report` /
  `ci-dispatch-e2e` / `test-agents-e2e` make targets and CI jobs.
- **Remove the dispatcher tests:** `tests/test_watchloop_dispatch.py`,
  `tests/test_install_watchloop_cron.py`, `tests/test_watch_report.py`,
  `tests/test_watchloop_dispatch_e2e.py`, and their fixtures.
- **Keep the engine-bump rebase in CI:** `scripts/engine_bump_sync.py`,
  `scripts/engine_bump_rebase.py`, and `.github/workflows/engine-bump-rebase.yml`
  stay (issue #208).
- **Docs:** AGENTS.md and README drop the watch-loop / host-crontab sections.

## User-Visible Impact

No change to user-facing serving/model commands. The repo no longer installs a
host crontab and no longer spawns autonomous issue workers; the only background
automation is the CI engine-bump rebase job.

## Non-Goals

- No change to the engine-bump rebase CI job (issue #208) — it stays.
- No change to the engine-bump *creation* workflow (`engine-bump.yml`).
