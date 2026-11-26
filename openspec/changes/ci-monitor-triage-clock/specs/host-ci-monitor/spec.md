# Spec delta: host-ci-monitor (issue #3081)

## ADDED Requirements

### Requirement: the monitor reads the wall clock through one seam and its tests freeze their own clock

`scripts/ci_monitor.py` SHALL read the wall clock through exactly one module-level seam (`_utcnow()`)
used by the snapshot leg (`build_snapshot`) and the `--triage` leg; no other inline
`datetime.now(...)` call SHALL remain in the incident flow. The age window (`MONITOR_MAX_AGE_HOURS`)
SHALL stay live-time based in production, while the triage tests SHALL pin the seam to a fixed
instant so a hardcoded fixture payload never ages out when the real wall clock passes its own 72h
window: the routing/dedupe test pins the seam INSIDE the window (its assertions hold on any future
run date), and a companion test pins the seam PAST the window and asserts the aged path
(`no-completed-failed-run found aged=<n>`) instead of routing.

#### Scenario: the triage dedupe test passes on any future wall-clock date

- **Given** the recorded `HEAD_RUNS` payload whose red stamps sit on 2026-11-23/24 and the test's
  frozen seam at 2026-11-24T14:00:00Z (4 hours after the representative run, inside the window)
- **When** `pytest tests/test_ci_monitor.py -q` runs on ANY later real date
- **Then** the dedupe assertions hold (`routed=1 suppressed=1 aged=0`, the representative routed, the
  history and the green run not routed) and the test exits rc=0
- **Test:** `pytest tests/test_ci_monitor.py -q` (recorded payloads, no network)

#### Scenario: a clock frozen past the window ages every red out

- **Given** the same `HEAD_RUNS` payload with the seam frozen at 2026-12-01T00:00:00Z (7+ days past
  the red stamps, past `MONITOR_MAX_AGE_HOURS`)
- **When** `ci_monitor.main(["--triage"])` prints its verdicts
- **Then** nothing is routed for that PR, the verdict reads
  `TRIAGE-PR pr=3012 head=8c1def4f8 no-completed-failed-run found aged=2`, and no reactor call is made
- **Test:** `pytest tests/test_ci_monitor.py -q` (recorded payloads, no network)

#### Scenario: the incident flow keeps one clock read

- **Given** `scripts/ci_monitor.py`'s snapshot leg and `--triage` leg
- **When** either builds its age-filtered incident list
- **Then** both take `now` from the single `_utcnow()` seam (the module contains no other
  `datetime.now(` call)
- **Test:** `pytest tests/test_ci_monitor.py -q` source-shape test (issue #3047's
  read-only no-mutation-verbs source test is the precedent)
