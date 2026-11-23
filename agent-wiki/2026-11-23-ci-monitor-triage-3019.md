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
  +3 tests (`--file-only`: exactly one `issue create`, zero `workflow run`, zero claim comment; a
  same-repo `main` run never labelled FIFTH-PARTY; two routings of one failure class in one process
  file ONE issue — `already filed this tick`). Targeted battery rc=0, 48 passed, zero network
  (recorded payloads / PATH-stubbed `gh`).
- Live preview: `make -s ci-monitor-triage DRY=1` rc=0 against live `gh` reads — the board's ten
  `MAIN-RED` bot-lane runs all routed with `TRIAGE-*` verdict lines, supersession cancelled the
  stale ones, dry mode filed nothing.
- Live non-dry triage (first ever, 2026-11-23): `make -s ci-monitor-triage` rc=0 filed #3020 for
  the red `issue-bot` agent-leg preflight on main, deduped three repeats via the marker search —
  and filed a DUPLICATE #3021 for one class because GitHub issue search lags a just-filed issue by
  seconds. #3021 was closed as duplicate of #3020; the gap is now closed in code: the reactor keeps
  a process-local filed-marker set (`_TICK_FILED`) beside the search, tested in-tick.
- Host cron move DONE: job `857ee38c40ce` active on `llgenie-planner` (`every 30m`, monitor-gated on
  `llgenie_ci_monitor.py`, prompt runs `make ci-monitor-triage` FIRST, mirrored at
  `agents/llgenie-planner/prompts/llgenie-ci-monitor.md`); maintainer job `268e0a994763` paused;
  `make sync-agent-profile PROFILE=llgenie-planner` rc=0 after folding four live-ahead skill files
  into the tree. The AGENTS.md monitor-contract wording is protected-file work and is filed as #3022.

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
`feat/ci-monitor-pipeline-triage`; the live cron move onto the planner profile is DONE
(job `857ee38c40ce`, maintainer copy paused). AGENTS.md contract wording is deferred to #3022
(protected file, direct owner consent required).
