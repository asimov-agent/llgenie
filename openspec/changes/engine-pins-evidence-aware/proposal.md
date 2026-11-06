# engine-pins-evidence-aware — proposal

Issue: [#1844](https://github.com/asimov-agent/llgenie/issues/1844)

## Why

The `engine-pins` job (added in #1696's ci.yml diff) polls up to `WAIT=290`
minutes for a repinned engine image to appear on GHCR then self-fails at the
`timeout-minutes: 300` ceiling. When the pin-producing engine-build cell is
red, NO image can ever be published, so every #1696 cycle today burns ~5
runner-hours on a deterministic timer-based fail — the worst kind of red:
cannot be diagnosed, cannot be fixed by re-running. The reigning proof is the
#1848 AC-2 re-probe (**run 42249201251** @ `main` `5bb742b2c2`, 26/29,
concluded `failure`) — three red producing cells measured from the fresh logs:
`engine-build-vllm-rocm` (job 127999598828, poetry/rocm==0.1.0 → #1558),
`engine-build-vllm-cuda` (job 127999598717, buildcache-cuda → #1843),
`engine-build-tensorfold-cuda` (job 127999598844, ghcr 403 → #1843). Earlier
evidence runs 42180155067, 42191768243 (vllm cpu serve-leg #1440, tensorfold
cache-write #1842) made the same point.

## What Changes

- **`scripts/check_engine_pins_published.py`** — `check()` gains an
  **evidence-aware pre-poll** (issue #1844): when CI asks for a wait AND names
  repo+branch, it reads the newest completed engine-build dispatch run's
  per-engine cell conclusions before polling; a repinned engine whose producing
  cell already concluded red prints a recorded **`SKIPPED`** decision (engine,
  run id, red conclusion) and returns 0 instead of burning the wait.
- **`_producer_cell_conclusions`** — gh-based read of the producer's cell job
  state (issue #893's `actions: read` pattern, mirrors
  `engine_build_trigger._branch_producers`/`_run_builds_engine`).
- **`.github/workflows/ci.yml`** — `engine-pins` job passes `REPO`+`BRANCH`
  (`actions: read` granted) to turn the pre-poll on.
- **`Makefile`** — target passes `--repo`/`--branch`.
- **`tests/test_check_engine_pins_published.py`** — hermetic tests: red cell
  skips (AC1), success cell + 404 tag still reds / non-success-not-red /
  in-progress waits (gate not weakened, AC2), pre-poll off without wait or
  repo+branch (hermetic), ci wiring.
- Rendered decision: do NOT delete the job and do NOT silently shrink `WAIT` —
  a shorter bound is a silent ratchet; the evidence-aware skip is the truthful
  fix (the red belongs to the producing cell, not a timer).
