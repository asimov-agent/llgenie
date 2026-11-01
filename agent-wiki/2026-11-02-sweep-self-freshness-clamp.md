# 2026-11-02 sweep self-freshness clamp (issue #1291)

The all-pipelines sweep (`.github/workflows/all-pipelines.yml`, weekly Saturday 04:27 UTC) is itself a
pipeline — and a gate nobody runs is not a gate. Before this change the sweep could red a down daily
security scan (#1285) but could never red *itself*: a stopped weekly sweep read as clean wallpaper
exactly the way a stopped daily scan used to, and there was no binding alarm for "nobody ran the
observatory this week". This change clamps the sweep's OWN freshness (observatory-of-observatories):

- `scripts/all_pipelines.py`: new `SWEEP_GATE_MAX_AGE_HOURS` (= 168×2 + 2 h, one missed weekly slot +
  margin — mirrors the daily `ADMISSION_GATE_MAX_AGE_HOURS = 50` reasoning) and `SWEEP_UNSEEN_MARK`.
  `sweep()` reads the sweep workflow's own previous CONCLUDED run via a new `sweep_self_run` helper
  (it skips the currently-executing run, which is fresh by construction and would make the check
  self-fulfilling); a missing or older-than-cadence previous run sets `sweep_unseen`, which
  `render_report` renders as a `SWEEP UNSEEN (last run \<date\> @ \<sha\>)` line and FAILS the sweep
  (exit 1). The #1285 daily admission-down/stale alarm is untouched and still fires.
- `tests/test_all_pipelines.py`: `make_stub` now serves the sweep's own workflow runs (default fresh,
  overridable for the negative control); 3 new tests — stale self-run → `SWEEP UNSEEN` + exit 1
  (negative control, last-run age stubbed past the window), fresh self-run → green, and stale-self +
  disabled-gate → both alarms fire together (acceptance #3).
- `docs/SECURITY.md` + `docs/BOTS.md`: the sweep's own freshness is part of the gate discipline — a
  weekly sweep older than its cadence is admission-stale, same as a daily scan.

Not covered (per the issue): restoring a down scan or re-running a stale sweep is lane action, not a
gate; alarming on a reader who ignores a report is review hygiene, not a CI gate.

Verified: `scripts/all_pipelines.py` + the stub driver exercise all five sweep paths green (stale→red,
fresh→green, both-fire, gate-alone, gate-stale); `make check-workflows check-wiring check-docs lint`
gate list.

References: implements issue #1291.
