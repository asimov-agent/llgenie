# 2026-11-26 — the monitor reads the wall clock through one seam, so triage fixtures never age out (issue #3081)

## What was verified against the issue

- The fuse was reproduced before the fix: at `origin/main 3cea715e3`
  `~/llama-gguf-tools/.venv/bin/python3 -m pytest tests/test_ci_monitor.py -q` fails
  `test_triage_routes_main_red_and_pr_check_incidents` (line 215, measured 2026-11-26T12:25Z) with
  `no-completed-failed-run found aged=2` against the asserted `routed=1 suppressed=1 aged=0`. The
  fixture's red stamps (`HEAD_RUNS` updatedAt 2026-11-23/24) crossed their own
  `MONITOR_MAX_AGE_HOURS = 72` window in real time, and the same single test was the only unit red
  in both open lanes (CI runs 45798167547 and 45799421620).
- The fix shape matches the issue: `scripts/ci_monitor.py::_utcnow()` is now the module's ONE
  `datetime.now(` call — the snapshot leg (`build_snapshot`) and the `--triage` leg take `now` from
  it; `MONITOR_MAX_AGE_HOURS` and `_aged_out` keep their live-time behaviour untouched.
- The tests freeze their own clock through the seam: the dedupe test pins `_utcnow()` at
  2026-11-24T14:00:00Z (inside the window, 4 h after the representative run), a new test
  `test_triage_ages_every_red_when_the_clock_runs_past_the_window` pins it at 2026-12-01T00:00:00Z —
  past the window — and asserts the aged verdict (`no-completed-failed-run found aged=2`) with zero
  routings for the head, and a source-shape test pins the one-clock rule (precedent: the #3047
  no-mutation-verbs source test). The plan-level tests already pinned their own `NOW`; they stayed.
- Audit for sibling fuses: every other wall-clock-sensitive path was checked — the dry-preview test
  asserts only unstamped MAIN-RED lines, the supersession triage test passes
  `--max-age-hours 1000000`, and `snapshot_lines` with no `now` never age-filters. No second time
  bomb in the file.

## Key decisions

- Freeze the seam in tests rather than injecting a `--now` CLI knob: production keeps live-time
  ageing (the monitor must age real runs), and the test suite gets determinism without a new knob
  to keep honest.

## Current status

- Landed behaviour: `tests/test_ci_monitor.py` 26 passed, clock-independent at any future run date
  (issue #3081).
