# 2026-11-12 — dispatch-observability (#2578 / PR pending)

## What was verified

- Premise measured in #2570: cron-fired engine-build dispatches (waves 43211663538..
  43211688780, 43206254966-era storms) sat in the queue with no metadata naming the liveness
  run that fired them; cancellation decisions needed log spelunking every time.
- Fix wired in BOTH directions: `.github/workflows/registry-liveness.yml` passes
  `-f producer_run="${{ github.run_id }}"` on both dispatch shapes (coalesced sweep per
  #2579, single cell per #2567); `.github/workflows/engine-build.yml` accepts `producer_run`
  (default empty) and its guard job runs a "Dispatch provenance" step printing
  `dispatched_by_run=<id>` + writing the producer into `$GITHUB_STEP_SUMMARY`. An unattributed
  dispatch (human or PR-lane) records `dispatched_by_run=none-recorded actor=<actor>`.
- The PR-lane trigger (`engine-build-pr-trigger`) dispatches unchanged: its own awaited-verdict
  log already names every producer run id it dispatches.

## Decisions

- Text lock lives beside the other registry-liveness locks in
  `tests/test_check_engine_pins_published.py`
  (`test_liveness_dispatches_name_their_producer_run`): both dispatch call sites must carry
  the field, the input roster must hold `producer_run`, and the provenance step must echo into
  log AND summary with the explicit `none-recorded` fallback.

## Current status

- OpenSpec change `dispatch-observability` validates; targeted pytest green; full `make
  test-unit` running before push.
