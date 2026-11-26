# 2026-11-26 — ci-monitor triage test no longer ages with the wall clock (#3081)

`tests/test_ci_monitor.py::test_triage_routes_main_red_and_pr_check_incidents` carried recorded
head-run stamps of 2026-11-23T10:00Z / 2026-11-24T10:00Z, while `scripts/ci_monitor.py::main`
(line 508) reads the real `datetime.now(timezone.utc)` and `_aged_out` (line 146) applies
`MONITOR_MAX_AGE_HOURS = 72`. Past 2026-11-27T10:00Z the representative head run aged out, and
the line became `PR-ROUTE pr=3012 head=8c1def4f8 routed=1 suppressed=0 aged=1 uncovered=lane B`
instead of the asserted `suppressed=1 aged=0`. Reproduced locally at `origin/main` `3cea715e3`
on 2026-11-26T13:15Z (`1 failed`, `tests/test_ci_monitor.py:215`); the same fixture reddened
`linux / unit` on both open PRs (runs `45798167547` #3079, `45799421620` #3030), so the board
jammed on a fixture, not on any branch's code.

## Change

- `_freeze_monitor_clock(monkeypatch, now)` pins `ci_monitor.datetime` in the test's own
  namespace with a `FrozenDatetime` subclass whose `now(tz)` returns the fixed instant;
  `fromisoformat` is inherited, so `_aged_out` still parses stamps normally. **Production is
  unchanged**: `MONITOR_MAX_AGE_HOURS`, `_aged_out`, and `main`'s live clock read are identical
  to base (`git diff -- scripts/ci_monitor.py` is empty).
- `_head_runs_at(now)` re-stamps the recorded head runs relative to that same frozen clock,
  keeping their relative ages (representative 24h, same-bucket history 48h, green 22h — all
  inside the 72h window). The fixture's relative ages are what the assertion describes.
- The test is parametrized over **both sides** of the old fuse — `2026-11-26T09:00Z` (before)
  and `2026-11-28T12:00Z` (past `2026-11-27T10:00Z`) — and emits the byte-identical asserted
  line in both. `2 passed` rc=0 for the two-param test; `25 passed` rc=0 for the full file.

## Not covered

The two open lanes' own body/commit defects remain their owners' work; no gate was weakened,
no ageing constant changed, and no PR branch was edited.
