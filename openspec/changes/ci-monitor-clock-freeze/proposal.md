# Change: freeze the ci-monitor triage test clock

## Why

Issue #3081: `tests/test_ci_monitor.py::test_triage_routes_main_red_and_pr_check_incidents`
uses recorded head runs stamped `2026-11-23T10:00:00Z` / `2026-11-24T10:00:00Z`, but
`scripts/ci_monitor.py::main` reads the real wall clock (`now = datetime.now(timezone.utc)`,
line 508) and `_aged_out` (line 146) compares against `MONITOR_MAX_AGE_HOURS = 72`. Past
2026-11-27T10:00Z the representative head run ages out, so the line becomes
`PR-ROUTE … routed=1 suppressed=0 aged=1` instead of the asserted `suppressed=1 aged=0`.

Measured locally at `origin/main` `3cea715e3` on 2026-11-26T13:15Z (pytest),
`1 failed, tests/test_ci_monitor.py:215`. The same fixture red makes `linux / unit` fail on
both open PRs (runs `45798167547` #3079 and `45799421620` #3030) — the board jams on a
fixture, not on any branch's code, and every lane opened after the fuse burns reads as a
regression.

## What Changes

- The triage test pins the `now` its snapshot reads by monkeypatching `ci_monitor.datetime`
  with a frozen clock seam, so the recorded head runs' ages are relative to the test's own
  clock rather than to the real wall clock. The head-run stamps are derived from that same
  frozen `now`, preserving the fixture's relative ages (representative 24h old, history 48h
  old, green 22h old) — all inside the 72h window.
- The test is parametrized over both sides of the original 2026-11-27T10:00Z fuse: a clock
  before it and a clock past it. Both produce the byte-identical asserted line, proving the
  time-bomb is gone rather than moved.
- **Production ageing is untouched**: `MONITOR_MAX_AGE_HOURS = 72`, `_aged_out`, and
  `main`'s live `datetime.now(timezone.utc)` remain exactly as they are; only the test
  freezes a clock in its own module namespace via `monkeypatch`.

## Benefit

The unit battery stops red-firing a wall-clock fixture on every PR: #3079 and #3030 clear
their unit red once the fix lands on main, and every future lane starts green. Production
triage keeps its real-time ageing semantics behind a deterministic, replayable test.

## Not covered

- The two open lanes' own body/commit defects (their owners handle them). No gate is
  weakened, no ageing constant is changed, and no PR branch is edited by this change.
