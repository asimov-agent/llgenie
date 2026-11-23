# CI monitor triage: failed main/PR pipelines file issues automatically (issue #3019)

Date: 2026-11-23. Issue: #3019. OpenSpec change: `ci-monitor-pipeline-triage`.

## What was verified
- `scripts/ci_monitor.py --triage` routes the incident snapshot it already builds: every `MAIN-RED`
  run and every `PR-CHECKS` incident's completed failed runs (resolved via the seam's
  `gh run list -c <head-sha>`, filtered to `MAIN_RED_CONCLUSIONS`) go to the run-failure reactor in
  `--file-only` mode — marker-deduped six-section issues, one `TRIAGE-*` verdict line per routing,
  `DRY=1` previews without filing, `MONITOR-OK`/`MONITOR-ERROR` route nothing.
- `scripts/run_failure_reactor.py --file-only` overrides Route A's dispatch: a pushable PR head's
  failure falls through to Route B's filing path — same `issue_body.render`, same marker dedupe, same
  lane-label classifier, same supersession guard — and no `gh workflow run` is reachable from the
  host path. Dispatching the fix-bot stays a CI/human action (AGENTS: no host queue-pumping).
- Make wiring: `make ci-monitor-triage` (`mk/bots.mk`, `DRY=1` preview) + `FILE_ONLY=1` knob on
  `make run-failure-reactor`. No `package-layers.json` edge needed: `ci_monitor` and
  `run_failure_reactor` share the "Bots and automation" group.
- Tests: `tests/test_ci_monitor.py` +5 triage tests (routing, dry, clean-board no-route,
  no-failed-run line, seam filter through a stubbed `run_checked`); `tests/test_run_failure_reactor.py`
  +2 tests (`--file-only`: exactly one `issue create`, zero `workflow run`, zero claim comment; a
  same-repo `main` run never labelled FIFTH-PARTY). Targeted
  battery rc=0, 47 passed, zero network (recorded payloads / PATH-stubbed `gh`).
- Live preview: `make -s ci-monitor-triage DRY=1` rc=0 against live `gh` reads — the board's ten
  `MAIN-RED` bot-lane runs all routed with `TRIAGE-*` verdict lines, supersession cancelled the
  stale ones, dry mode filed nothing.

## Key decision
Triage reuses the reactor's decision logic rather than duplicating filing in the monitor (one code
path); the host path files tracked issues and dispatches nothing. The sanctioned monitor cron moves
from the `llgenie-ci-pipelines-maintainer` profile to the `llgenie-planner` profile so the tick feeds
the profile that drives the board, and its prompt runs `make ci-monitor-triage` FIRST. The tick also
carries the pacing rules: while a pushed lane's CI runs the agent starts the next board issue (no
idle polling); a failed PR pipeline on a lane the agent owns is fixed ON THAT BRANCH (pushed
commits; `agent:ci-pipelines-maintainer` for pipeline/gate failures, `agent:implement` otherwise).

## Current status
Script, reactor mode, targets, tests, agents tree, and docs on branch
`feat/ci-monitor-pipeline-triage`; the live cron re-registration onto the planner profile happens
in the same landing as the PR (host-side action, not a repo file).
