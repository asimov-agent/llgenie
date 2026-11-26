# Change: the monitor reads the wall clock through one seam, so triage tests never age out

## Why

Issue #3081: `tests/test_ci_monitor.py::test_triage_routes_main_red_and_pr_check_incidents` carries
hardcoded fixture timestamps (`HEAD_RUNS` `updatedAt` 2026-11-23T10:00:00Z / 2026-11-24T10:00:00Z),
but the `--triage` path reads the REAL wall clock: `scripts/ci_monitor.py` calls
`datetime.now(timezone.utc)` inline (snapshot leg line ~462, triage leg line ~508) and `_aged_out`
compares the stamps against `MONITOR_MAX_AGE_HOURS = 72`. Once real time passes the fixture's own
72-hour window, the representative failure run is aged out and the printed line becomes
`no-completed-failed-run found aged=2` instead of the asserted `routed=1 suppressed=1 aged=0`. The
test passed at merge time (PR #3047, 2026-11-24) and began failing 72h later: measured local red at
`origin/main 3cea715e3` (`1 failed tests/test_ci_monitor.py:215`, line printed 2026-11-26T12:25Z),
and red in the `linux / unit` lane of both open PRs — CI runs 45798167547 (#3079) and 45799421620
(#3030). Every future PR lane reds on this fixture.

## What Changes

- `scripts/ci_monitor.py` gains ONE wall-clock seam, `_utcnow()`, used by the snapshot leg
  (`build_snapshot`) and the `--triage` leg where the inline `datetime.now(timezone.utc)` calls sit
  today. Production age semantics are untouched: the age window stays live-time based.
- The triage tests freeze their own clock through that seam: the dedupe test pins `_utcnow()` to a
  fixed instant inside the fixture's window (4h after the representative run), so its assertions hold
  on any future run date.
- A new test pins the seam PAST the window and asserts the aged path (`no-completed-failed-run found
  aged=2`), so production ageing keeps a deterministic test behind it.

## Out of Scope

- Changing `MONITOR_MAX_AGE_HOURS` semantics or any production routing behaviour.
- The `check-pr-commit-checkboxes` guard red on PR #3079 — that is #3079's own commit-message body,
  fixed on its branch.
