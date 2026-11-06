# 2026-11-06 an engine/build step is never unbounded (issue #1865)

The #1696 engine-build zombies (runs `42191808660`/`42191768249`, started 09:00Z, still
`in_progress` at `a90fb89aec` 3h35m later) stalled every push=true run behind the engine-build
concurrency gate with no bound to exceed and no fault surfaced — indistinguishable from a genuinely
long build. That is the #1250/#1860 class this contract ends.

The change is two halves, both landing together:
- A **CONTRACT/standing-rule line** (versioned via #791) in the ci-pipelines lane skill: every
  engine/build job declares a maximum runtime (`timeout-minutes`); on overrun the step is surfaced
  (the #1860 stall-watchdog names the concurrency-gate holder) and it is eligible for truncation —
  a step never runs unbounded.
- A **guard that makes the bound testable**: `tests/test_engine_build_timeouts.py` asserts every
  job in `engine-build.yml` + `engine-build-pr-trigger.yml` carries `timeout-minutes`, so a future
  unbounded addition reds the suite. It proved red on the one genuinely unbounded job — the
  `matrix` job of `engine-build.yml` had no `timeout-minutes`, and this PR bounds it (10m, a
  sub-second `make engine-build-matrix` call is all it runs).

The build cells already carried the #1818 matrix-aware bound (240m, rocm 360m) and the trigger the
#1860 250m window; `matrix` was the gap. Verified: guard-prove (test red on old tree naming
`engine-build.yml::matrix`, green on fixed); the out-of-scope #1860/#1863 stall-watchdog product fix
is a separate already-merged vehicle. Live evidence for the #1696 class: runs
`42191808660`/`42191768249 @ a90fb89aec`.
