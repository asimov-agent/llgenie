# LLGenie Implementer: freshness-clamp the weekly admission sweep (#1289's observatory-of-observatories)

Implements issue #1291 (ready-for-review PR, never merged). The #1289 admission alarm reds the `all-pipelines`
weekly sweep when the *security-scan daily* cadence is down — but that alarm only ever reaches a reader when the
sweep itself runs AND is read. A sweep that stops running (or a reader who skips it) reads identically to one
that found everything clean, so a down daily scanner sits un-alarmed for up to a WEEK. Observatory of
observatories must itself be freshness-clamped. This adds the sweep's own freshness as a first-class red.

## What changed (measured on this worktree)

- **`scripts/all_pipelines.py`** — new `SWEEP_UNSEEN_MARK` and `SWEEP_GATE_MAX_AGE_HOURS = 24*8` (weekly
  cadence ~168 h + one missed slot + margin). New `sweep_self_last_run()` reads the sweep's OWN most recent
  COMPLETED run `(created_at, head_sha)` via `/actions/workflows/{id}/runs`, filtering to `completed` (the
  sweep is running right now, so the newest run is this in-progress one, age ~0); a failed/empty read returns
  `('', '')` = "never completed", treated exactly like a stale one. In `sweep()`, the SELF row is demoted to
  `sweep_unseen` when `not last or _age_hours(last) > SWEEP_GATE_MAX_AGE_HOURS`; `ok()` renders
  `SWEEP UNSEEN (issue #1291)`; `render_report` appends a `SWEEP UNSEEN (last run <date> @ <sha>)` alarm line,
  counts it in the summary, and the exit code becomes 1 on `sweep_unseen`.
- **`tests/test_all_pipelines.py`** — the stub `make_stub` gains `sweep_last_run`/`sweep_last_sha` served for
  the all-pipelines.ymls workflow's OWN id (defaulting to a fresh timestamp so incidental sweep() tests stay
  green). Two new tests: `test_a_stale_sweep_reds_with_a_sweep_unseen_line` (last COMPLETED run > cadence →
  exit 1, `SWEEP UNSEEN`, the sha named) and `test_a_fresh_sweep_is_not_marked_unseen` (recent → no alarm, 0).
- **Docs** — `docs/SECURITY.md` and `docs/BOTS.md` state that the sweep's own freshness is part of the
  admission-gate discipline (a weekly sweep older than its cadence is admission-stale, same as an aged daily
  scan); agent-wiki note + changes.d fragment + `CHANGES.md` row added.

## Verification (measured, not asserted)

- `python3 -m pytest tests/test_all_pipelines.py -q` (project venv) → **15 passed** (the 2 new freshness tests +
  all pre-existing gate/stale/sweep tests, including the #1285 daily-scan admission-down cases unchanged).
- `make check-workflows check-wiring check-docs lint` green at the head; `make ci-scope BASE=<base>` runs the
  CI job set this change class selects (scripts/tests/docs + the all-pipelines workflow).

## Not covered (from the issue)

- Actually restoring a down scan or re-running a stale sweep — that is a lane action, not a gate (restore
  mechanics live with #1285's operational half).
- Alarming when a reader skims a report without acting — review hygiene, not a CI gate.

## The #1289 relationship

The #1285/#1289 gate solved "is main unscanned today"; this issue solves "has anybody asked this week". The
daily-scan admission-down alarm is unchanged and still fires — the sweep-freshness clamp is additive, so a
silent watcher is now a red industrial alarm like the silent scanner it was meant to catch.
