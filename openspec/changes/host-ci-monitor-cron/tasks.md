# Tasks

## 1. Monitor script + target

- [x] 1.1 Write `scripts/ci_monitor.py`: injectable fetch seam (default `gh` reads through `scripts/proc.py`), deterministic sorted snapshot (`MAIN-RED`, `PR-CHECKS`, `PR-MERGE`, `PR-REVIEW`, `MONITOR-OK`, `MONITOR-ERROR gh-fetch-failed`), read-only.
- [x] 1.2 Add the `ci-monitor` target to `mk/bots.mk` (Makefile-included; help + target list, `CI_MONITOR_MAIN_LIMIT`/`CI_MONITOR_MAX_AGE_HOURS` knobs) running `python3 scripts/ci_monitor.py --repo $(GH_REPO)`; prove live: `make ci-monitor` rc=0 printing the current snapshot (proven: make -s ci-monitor rc=0, sha256-identical snapshots across two runs).

## 2. Tests

- [x] 2.1 Write `tests/test_ci_monitor.py` covering every scenario in `specs/host-ci-monitor/spec.md` through the injected seam; prove: `make test-unit` green with the new module collected (proven: pytest tests/test_ci_monitor.py 11 passed; full battery at the ship commit).

## 3. Docs + rules

- [x] 3.1 Rewrite the "Hermes cron jobs never run on the host" section of `AGENTS.md` into "Host cron: a blanket ban plus exactly one named exception" with the full monitor job contract; prove: `make check-docs` rc=0, `make check-agent-access` rc=0.
- [x] 3.2 Add `agent-wiki/2026-11-22-host-ci-monitor-cron-3013.md` + the `docs/changes.d` line naming #3013.

## 4. Gates

- [x] 4.1 Prove pre-push: `make openspec-validate NAME=host-ci-monitor-cron` rc=0 and `make check-wiring` rc=0 measured at the measured tree; `make lane-preflight` preflight: OK on the shipped head (the commit adds only this tick to the measured tree).
