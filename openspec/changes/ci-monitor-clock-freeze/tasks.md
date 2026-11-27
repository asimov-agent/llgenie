# Tasks: freeze the ci-monitor triage test clock

## 1. Spec first

- [x] OpenSpec change `ci-monitor-clock-freeze` created through `make openspec-new` with
      proposal, spec delta and this task list before any code edit.

## 2. Pin the test clock, keep production ageing

- [x] `tests/test_ci_monitor.py::test_triage_routes_main_red_and_pr_check_incidents` freezes
      `ci_monitor.datetime` through `monkeypatch` so `main`'s `now` is deterministic.
- [x] The test's head-run `updatedAt` stamps derive from that same frozen `now`, preserving
      the relative ages (24h/48h/22h) that make the `aged=0 suppressed=1` assertion true.
- [x] The test runs at two frozen clocks (before and after 2026-11-27T10:00Z) and the
      asserted `PR-ROUTE … suppressed=1 aged=0` line is byte-identical in both.
- [x] `scripts/ci_monitor.py` is unchanged: `MONITOR_MAX_AGE_HOURS = 72`, `_aged_out` and
      `main`'s live clock read are the same as at base (`git diff` empty).

## 3. Prove it

- [x] `python -m pytest tests/test_ci_monitor.py -q` rc=0 in the container at the fix head
      (25 passed); the two-parametrized test alone is `2 passed` rc=0.
- [x] `make test-unit` rc=0 at the fix head (4540 passed, 13638 deselected in 1027.80s).
- [x] `make openspec-validate NAME=ci-monitor-clock-freeze` rc=0 and the wiring/docs gates
      are green.
- [x] Negative control: reverting the clock freeze reddens the test at the real wall clock
      (`1 failed`, `tests/test_ci_monitor.py:215`, `suppressed=0 aged=1`); restoring it greens
      both frozen sides — the fix, not luck, is what makes the suite pass.
