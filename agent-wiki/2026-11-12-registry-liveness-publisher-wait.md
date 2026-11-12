# 2026-11-12 registry-liveness publisher-wait (#2592)

## What changed

`registry-liveness` (`.github/workflows/registry-liveness.yml`) triggers on every push to `main` and
hard-fails (rc=1) when a committed engine pin's tag resolves `manifest unknown` in GHCR. But a merge
push races the run that PUBLISHES the pins in this tree — the `ci.yml` run at the same head SHA. So on
a retag merge liveness redded on a tag its own merge-CI was about to publish. Measured: run #457
(head `be92a32695`) redded `mlx:93e6d4a6-e5ab3798-cpu resolves no manifest` at 19:23:12Z while CI
#5565 at the same head was still `in_progress`; the tag is published now. #454/#455 redded
`85be1b6a87` the same way. The identical race then DISPATCHED engine-build sweeps (#682/#684 at
`85be1b6a87`) that failed `vllm-rocm ... Permission denied` — a second red reproducing the very
failure the tree had already fixed only in `b32594c8c4`.

## The fix

- A before-fleet step (push-trigger only) waits, bounded, for the same-head `ci.yml` run to conclude,
  and records its verdict (`publisher_run` / `publisher_conclusion` / `publisher_failed` /
  `publisher_still_running`).
- A pin still in flight at the wait bound is mid-publish, not missing: the fleet gate's hard-fail is
  suppressed (rc forced green), the filer and dispatch no-op, and the verdict is deferred to a
  non-racing (scheduled) run.
- A publisher that concluded FAILURE means the pin is unpublished because its own main run failed: no
  sweep is dispatched (it would reproduce the failure), and the tracking issue names the failed
  publisher run as the diagnostic anchor.
- A scheduled run (no same-head publisher) and a push run whose publisher concluded SUCCESS keep
  today's contract verbatim: ALL=1 hard-fail + file one tracking issue per missing cell + dispatch
  per the `[select]` contract (#2259/#2190 semantics unchanged).

The wait gate is workflow-only; `scripts/check_engine_launchers.py` is behaviourally untouched.

## Verified

- `make check-workflows` parses every `${{ }}` and the edited YAML (stdonly gate).
- `tests/test_check_engine_pins_published.py` — the new wiring tests
  (`test_push_run_waits_for_the_same_head_publisher_before_the_manifest_check`,
  `test_publisher_still_in_flight_does_not_hard_fail`,
  `test_no_sweep_dispatched_for_a_failed_publisher`,
  `test_scheduled_and_successful_publisher_keep_the_dispatch_contract`) plus the pre-existing
  count-sensitive liveness tests (dispatch shapes `==2`, `>> tracking_issues.txt ==2`,
  `-f producer_run==2`, `done < select.txt ==1`, ALL=1 / `exit "$rc"` / `fleet_rc=` preserved).

Issue: [#2592](https://github.com/asimov-agent/llgenie/issues/2592). PR: the `registry-liveness-publisher-wait`
change's own PR (`closes #2592`).
