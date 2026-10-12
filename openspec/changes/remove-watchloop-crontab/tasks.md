# remove-watchloop-crontab

## Remove the host crontab plumbing

- [x] 1.1 Delete `scripts/install_watchloop_cron.py`.
- [x] 1.2 Remove `cron-install` / `cron-uninstall` / `cron-snapshot` make targets
      and the `ci-cron` job from the Makefile.
- [x] 1.3 Remove the `cron` job from `.github/workflows/pipeline.yml`.

## Remove the dispatcher

- [x] 2.1 Delete `scripts/watchloop_dispatch.py`, `scripts/watch_report.py`,
      `scripts/serialized-make.py`, and `scripts/worker-model.template`.
- [x] 2.2 Remove `watch-report` / `ci-watch-report` / `ci-dispatch-e2e` /
      `test-agents-e2e` make targets and the `watch-report` / `dispatch-e2e` CI
      jobs.
- [x] 2.3 Delete the dispatcher tests + fixtures
      (`test_watchloop_dispatch.py`, `test_install_watchloop_cron.py`,
      `test_watch_report.py`, `test_watchloop_dispatch_e2e.py`, and their
      fixtures).

## Keep the engine-bump rebase in CI

- [x] 3.1 Confirm `scripts/engine_bump_sync.py`, `scripts/engine_bump_rebase.py`,
      and `.github/workflows/engine-bump-rebase.yml` remain.

## Docs

- [x] 4.1 AGENTS.md drops the watch-loop / host-crontab sections.
- [x] 4.2 README drops the watch-loop / host-crontab sections.

## Tests

- [x] 5.1 `tests/test_remove_watchloop.py` — no cron make targets; dispatcher
      files gone; engine-bump rebase remains.

## Verification

- [x] 6.1 `make openspec-validate NAME=remove-watchloop-crontab` exit 0.
- [x] 6.2 `make test-unit` green.
- [x] 6.3 `make lint` clean.
- [x] 6.4 Pushed to the feature branch; PR opened against `main` referencing the
      issue; issue + PR bodies aligned.
