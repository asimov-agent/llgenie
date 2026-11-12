# Proposal: dispatch-observability

## Why

Issue #2578: engine-build dispatches fired by the scheduled registry-liveness run arrive in the
queue indistinguishable from a human dispatch. Issue #2570 measured dispatch waves
(43206254966-era storms) that flooded the `engine-build-push` concurrency group; deciding which
queued runs to cancel required log archaeology every time, because no queued engine-build run
named the run that fired it. After the #2579 coalescing (#2580 merged), liveness dispatches are
rarer but still anonymous — attribution is the missing half of the wave story.

## What Changes

- `engine-build.yml` gains a `producer_run` dispatch input (default empty) and a
  "Dispatch provenance" step in the guard job that records, into the run's own log AND
  `$GITHUB_STEP_SUMMARY`, the producing run id when present — or the triggering actor when a
  human dispatched without it.
- `registry-liveness.yml` passes `-f producer_run="${{ github.run_id }}"` on BOTH dispatch
  shapes (the #2579 coalesced sweep and the #2567 single-cell dispatch), so every liveness-fired
  producer run is attributable from its own metadata in one lookup.
- A new text-lock test pins both sides of the wiring (issue #2578's AC).

## Not covered

Actor-level audit (distinguishing cron vs manual dispatch in the API) beyond the recorded producer
run id — unchanged from the issue body. The PR-lane trigger (`engine-build-pr-trigger`) already
names each producer run id in its own awaited-verdict log, so it dispatches unchanged.

## Impact

- Affected specs: dispatch-observability (new)
- Affected code: `.github/workflows/engine-build.yml`, `.github/workflows/registry-liveness.yml`,
  `tests/test_check_engine_pins_published.py`
