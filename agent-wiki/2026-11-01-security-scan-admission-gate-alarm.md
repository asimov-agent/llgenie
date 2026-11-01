# 2026-11-01 security-scan admission gate alarm (issue #1285)

The all-pipelines sweep treated `security-scan.yml` `disabled_manually` as a benign `DISABLED` row
and exited 0 — a down daily scan left `main` with no "is a package old today" answer and no alarm
(issue #1285, measured: `gh workflow list` state `disabled_manually`, no run since 2026-10-28). This
change makes the daily scan an **admission gate** whose disabled-or-never-ran state is a red run:

- `scripts/all_pipelines.py`: `SECURITY_GATE`/`ADMISSION_GATE_MAX_AGE_HOURS` constants; `classify`
  renders a `disabled_manually` gate as `admission_down`; a new `security_gate_last_run` freshness
  check demotes an active gate with no run within the 50 h daily-cadence window to `admission_stale`;
  `render_report` names each in a dedicated alarm line and fails the sweep (exit 1) for either.
- `tests/test_all_pipelines.py`: 4 new tests (disabled→red, ordinary-disabled stays benign,
  never-ran-active→stale+red, fresh-active→swept normally) + the umbrella dispatch test updated to
  assert the alarm instead of the old "exit 0" behaviour.
- `docs/BOTS.md` + `docs/SECURITY.md`: document the admission-gate alarm and that a silent scan is
  now a gated condition.

Verified: `tests/test_all_pipelines.py` all pass; `scripts/lane_preflight.py run` gates pass on the
committed tree. Restore side of #1285 (the `bots_restore_health.py measure` queue-health reading and
the `gh workflow enable` re-enable) is the operational half handled per #902's recorded condition.

References: implements issue #1285. The operational restore half (queue-health measurement, `gh
workflow enable`) is recorded on issue #1285 as the #902 restore-condition reading.
