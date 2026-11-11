# llgenie watch-loop invocation (removed; only the CI engine-bump rebase remains)

## The dispatcher and host crontab are REMOVED

`scripts/watchloop_dispatch.py` (the autonomous-issue dispatcher: merge gate,
issue spawner, stuck-PR repair, stale-worktree cleanup) and its host crontab
(`*/20 * * * *`, installed by `make cron-install` ->
`scripts/install_watchloop_cron.py`) are **removed from the repo**. The user's
standing decision: the repo must not depend on a dev machine's crontab, and
autonomous issue-working is out of scope. Do not re-add a host crontab or a
dispatcher; the only background automation is the CI engine-bump rebase.

Removed with the dispatcher: `watchloop_dispatch.py`, `watch_report.py`,
`install_watchloop_cron.py`, `serialized-make.py`, `worker-model.template`, the
`cron-*` / `watch-report` / `ci-cron` / `ci-watch-report` / `ci-dispatch-e2e` /
`test-agents-e2e` make targets, the `cron` / `watch-report` / `dispatch-e2e`
pipeline jobs, and the dispatcher tests + fixtures.

## The ONE CI cron that touches engine-bump PRs

- `engine-bump.yml` (weekly, `23 6 * * 1`) only **creates** the
  `chore/engine-bump-*` PRs.
- `engine-bump-rebase.yml` (daily, `17 5 * * *`) **keeps them rebased**: it
  finds every open `chore/engine-bump-*` PR and, when one is behind `main`,
  forward-merges the latest `main` into it and force-with-lease-pushes it back.

The rebase logic lives in `scripts/engine_bump_sync.py` (the one
implementation: `is_engine_bump_pr`, `upstream_remote`/`main`,
`sync_pr_with_main`), imported by the CI entrypoint
`scripts/engine_bump_rebase.py`. The functions are parameterized by
`repo`/`run_git`/`log` so a caller injects its own git runner and logger.

So when someone asks "should the rebase be a CI cron?" the answer is: it IS a
CI cron (`engine-bump-rebase.yml`), and that is the only place it runs.

## Scope: ONLY the engine-bump PRs rebase against upstream main

`sync_pr_with_main` forward-merges the UPSTREAM `asimov-agent/main` ONLY for
engine-bump PRs (`chore/engine-bump-*` head ref, or head repo
`asimov-agent/llgenie`). Worker `feat/*` PRs live on the fork and are synced
against `origin/main` as before. Do not broaden this to "all PRs rebase against
upstream main" — the engine-bump branches are the only ones that live on the
upstream (not the fork), so they are the only ones that stalled at the
never-merge-behind gate on a fork-origin clone. The CI rebase entrypoint
filters to `chore/engine-bump-*` for the same reason.

## Checking whether a host entry exists (legacy / other machines)

```bash
crontab -l | grep -cE '^\s*\*/20|watchloop|llgenie'   # 0 = not installed
```

Also check `/etc/crontab`, `/etc/cron.d/`, root crontab, and systemd timers
before concluding an entry exists anywhere. The watch loop historically ran on
the macOS dev machine, not on a Linux host, so a Linux host's crontab may
legitimately have no entry. If a stale entry is found on a machine, remove it
with `crontab -e` (the `make cron-uninstall` target no longer exists).

## Pitfall: the user's "remove the cron" scope can be the WHOLE dispatcher

When the user says "remove the cron jobs", the scope is not always the narrow
host-crontab entry. In this repo the user chose to remove the entire dispatcher
and host-crontab plumbing, keeping only the CI rebase. Ask/confirm the scope
before ripping out files: "just the crontab entry" vs "the whole dispatcher".
Once the user says "kill the host crontab entirely ... drop the rest of the
dispatcher", that is a full removal — delete the scripts, make targets, CI
jobs, tests, and docs together, and keep only the CI engine-bump rebase.

## After the removal: stale required checks on `main`

Deleting the `cron` / `watch-report` / `dispatch-e2e` pipeline jobs does NOT
remove them from `main`'s branch-protection required-checks list. The PR then
shows `linux / cron`, `linux / dispatch-e2e`, `linux / watch-report` as
"Expected — Waiting for status to be reported" forever (the jobs no longer
exist to report). This is a repo-settings change needing an admin on the
upstream; the agent's collaborator token 404s on branch-protection read/write
and cannot do it. Hand the user the exact `gh api -X PUT
.../branches/main/protection/required_status_checks` command (or the web-UI
path) and state it needs admin — do not claim you can clear the pending checks
or force-merge to `main`.
