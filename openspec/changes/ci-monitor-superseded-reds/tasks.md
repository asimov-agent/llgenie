# Tasks: ci-monitor-superseded-reds

## 1. Classify main runs by their newest completed run

- [x] 1.1 Add `classify_main_runs` to `scripts/ci_monitor.py`: group completed `headBranch == "main"`
      rows by `workflowName`, order by `(updatedAt, databaseId)`, judge the group by its newest
      completed run; return `(incidents, superseded)` and record `supersededBy` on each superseded
      run. `main_red_runs` becomes the incident-only view of the same classifier.
- [x] 1.2 `snapshot_lines` prints `MAIN-RED` for incidents only and `MAIN-SUPERSEDED run=… superseded_by=…`
      only when `include_superseded=True`; `triage_incidents` routes incidents only (proven: the
      classifier tests, `pytest tests/test_ci_monitor.py -q` rc=0).
- [x] 1.3 Wire the knob: `--include-superseded` in `scripts/ci_monitor.py` and `INCLUDE_SUPERSEDED`
      passthrough in `mk/bots.mk` for `ci-monitor` and `ci-monitor-triage` (proven: `make -s ci-monitor`
      and `make -s ci-monitor INCLUDE_SUPERSEDED=1` both rc=0 at the lane head).

## 2. Prove it on the recorded payloads and the live board

- [x] 2.1 Update the existing main-red tests to the classifier and add the new cases (red→green not an
      incident; newest-still-red still an incident and its older red superseded; a newer in-flight run
      does not supersede; the age window applies to the newest completed run; superseded shown under
      the knob but never routed) (proven: `pytest tests/test_ci_monitor.py -q` rc=0 at the lane head,
      no network). The existing age-window test is UPDATED, not duplicated.
- [x] 2.2 Live read at the lane head: `make -s ci-monitor` prints fewer `MAIN-RED` lines than the 14
      measured at `3afb43704`, prints no `MAIN-SUPERSEDED` line, and `INCLUDE_SUPERSEDED=1` prints the
      superseded reds each naming its superseder (measured: 2 incidents — `45259560508`
      ci-frozen-reaper, `45332197474` issue-bot — 0 superseded by default, 14 superseded under the knob,
      7 `PR-CHECKS`) (proven: `make -s ci-monitor` and `make -s ci-monitor INCLUDE_SUPERSEDED=1` rc=0).
- [x] 2.3 `make ci-monitor-triage DRY=1` at the lane head routes no superseded run and still routes
      each live main red (proven: `make ci-monitor-triage DRY=1` rc=0 — 2 `TRIAGE-MAIN`
      (`45332197474`, `45259560508`), 28 `TRIAGE-PR`, 0 `MAIN-SUPERSEDED`).
- [x] 2.4 Full battery green with zero skips (proven: `make test-unit` rc=0 at the lane head,
      `make -s test-unit-network` rc=0).

## 3. Gate it before the push

- [x] 3.1 `make lane-preflight` prints `preflight: OK` and `make openspec-validate
      NAME=ci-monitor-superseded-reds` exits 0 (proven: both rc=0 at the lane head).

Ship (not a checklist item): push `feat/ci-monitor-superseded-reds` to `origin`, stamp the PR body with
`make bot-stamp-body`, open the PR to `asimov-agent/llgenie:main` carrying `closes #3048` with the
acceptance mirror ticked in the PR body AND the issue body, then re-poll the PR until green and armed.
