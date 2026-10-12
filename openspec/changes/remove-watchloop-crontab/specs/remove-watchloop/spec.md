# remove-watchloop-crontab — spec of record

Capabilities this change removes: the watch-loop host crontab and the
autonomous-issue dispatcher, keeping only the CI engine-bump rebase.

## REMOVED Requirements

### Requirement: watch-loop host crontab install/uninstall

The `cron-install` / `cron-uninstall` / `cron-snapshot` make targets and
`scripts/install_watchloop_cron.py` MUST be removed. No `*/20 * * * *` host
crontab entry is installed for the repo.

#### Scenario: no cron make targets remain

- **WHEN** the Makefile is inspected
- **THEN** it has no `cron-install` / `cron-uninstall` / `cron-snapshot` targets
  and no `ci-cron` job
- **Test:** `tests/test_remove_watchloop.py::test_no_cron_make_targets`

### Requirement: dispatcher and its tests removed

`scripts/watchloop_dispatch.py`, `scripts/watch_report.py`,
`scripts/serialized-make.py`, `scripts/worker-model.template`, and their tests
(`test_watchloop_dispatch.py`, `test_install_watchloop_cron.py`,
`test_watch_report.py`, `test_watchloop_dispatch_e2e.py`) MUST be removed, along
with the `watch-report` / `ci-watch-report` / `ci-dispatch-e2e` /
`test-agents-e2e` make targets and the `cron` / `watch-report` / `dispatch-e2e`
CI jobs.

#### Scenario: dispatcher files are gone

- **WHEN** the repo is inspected
- **THEN** `scripts/watchloop_dispatch.py` and `scripts/watch_report.py` do not
  exist, and no test references them
- **Test:** `tests/test_remove_watchloop.py::test_dispatcher_files_removed`

### Requirement: engine-bump rebase stays in CI

`scripts/engine_bump_sync.py`, `scripts/engine_bump_rebase.py`, and
`.github/workflows/engine-bump-rebase.yml` MUST remain (issue #208), so the
open `chore/engine-bump-*` PRs are still rebased onto the latest `main` by the
daily CI job.

#### Scenario: engine-bump rebase CI job remains

- **WHEN** the repo is inspected
- **THEN** the engine-bump rebase workflow, sync module, and entrypoint still
  exist
- **Test:** `tests/test_remove_watchloop.py::test_engine_bump_rebase_remains`
