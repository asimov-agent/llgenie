# Tasks: the monitor reads the wall clock through one seam, so triage tests never age out

## 1. One clock seam in the incident flow

- [x] `scripts/ci_monitor.py::_utcnow()` is the module's ONLY wall-clock read (returns
      `datetime.now(timezone.utc)`); `build_snapshot` and the `--triage` leg take `now` from it, and
      the inline `datetime.now(timezone.utc)` calls at the snapshot/triage sites are gone.
- [x] Production age semantics stay untouched: `MONITOR_MAX_AGE_HOURS` and `_aged_out` keep their
      live-time behaviour.

## 2. Tests freeze their own clock through the seam

- [x] `tests/test_ci_monitor.py` pins `ci_monitor._utcnow` in
      `test_triage_routes_main_red_and_pr_check_incidents` to 2026-11-24T14:00:00Z (inside the
      fixture's 72h window), so the dedupe assertions hold on any future run date.
- [x] A new test `test_triage_ages_every_red_when_the_clock_runs_past_the_window` pins the seam at
      2026-12-01T00:00:00Z and asserts `TRIAGE-PR pr=3012 head=8c1def4f8
      no-completed-failed-run found aged=2` with zero reactor routings.
- [x] A source-shape test asserts the incident flow contains exactly one `datetime.now(` call (the
      `_utcnow` seam itself).

## 3. Verification (pre-push proofs)

- [x] `~/llama-gguf-tools/.venv/bin/python3 -m pytest tests/test_ci_monitor.py -q` rc=0 at the head
      (whole file green, clock-independent).
- [x] `make lane-preflight` prints `preflight: OK` and `make openspec-validate
      NAME=ci-monitor-triage-clock` exits 0 at the head.

Ship actions (outside this checklist, after the proofs tick): push the branch, open the closing PR
against main, drive it green; CI lands it.
