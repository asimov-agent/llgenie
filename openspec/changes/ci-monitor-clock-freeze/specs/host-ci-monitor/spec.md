# Spec delta: host-ci-monitor (issue #3081)

## ADDED Requirements

### Requirement: the triage test's clock is frozen, not the wall clock

`tests/test_ci_monitor.py::test_triage_routes_main_red_and_pr_check_incidents` MUST pin the
`now` that `scripts/ci_monitor.py::main` reads (the `datetime.now(timezone.utc)` call at
line 508) by monkeypatching `ci_monitor.datetime` in the test's own namespace. The recorded
head runs used by that test MUST derive their `updatedAt` stamps from the same frozen `now`,
so their relative ages stay inside `MONITOR_MAX_AGE_HOURS = 72` regardless of when the suite
runs.

The test MUST be proven at two frozen clocks — one before and one after the original
2026-11-27T10:00Z fuse — with the byte-identical assertion
`PR-ROUTE pr=3012 head=8c1def4f8 routed=1 suppressed=1 aged=0 uncovered=lane B` at both.
Production ageing MUST NOT change: `MONITOR_MAX_AGE_HOURS`, `_aged_out`, and `main`'s live
clock read stay untouched, so a real monitor tick still ages runs out in wall-clock time.

#### Scenario: frozen clock before the original fuse

- **Given** the triage fixture head runs stamped relative to a frozen `now` of
  2026-11-26T09:00:00Z (before the old 72h fuse)
- **When** `ci_monitor.main(["--triage"])` runs with the frozen clock
- **Then** the plan routes one representative and reports `suppressed=1 aged=0`, and the
  assertion passes

#### Scenario: frozen clock past the original fuse

- **Given** the same fixture head runs stamped relative to a frozen `now` of
  2026-11-28T12:00:00Z (past the old 2026-11-27T10:00Z fuse that reddened the suite)
- **When** `ci_monitor.main(["--triage"])` runs with the frozen clock
- **Then** the printed line is byte-identical to the pre-fuse case (`suppressed=1 aged=0`)
  and the assertion passes — the wall clock no longer decides the result

#### Scenario: production ageing still uses wall-clock time

- **Given** the unmodified `scripts/ci_monitor.py` module
- **When** a real tick calls `main` without any test patch
- **Then** `now` is still `datetime.now(timezone.utc)` and runs older than
  `MONITOR_MAX_AGE_HOURS = 72` are still aged out — this change alters only the test
