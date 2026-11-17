# Trigger wait budget vs congested FIFO (issue #2892)

## What was verified

Issue #2892: the engine-build **trigger** failed every PR repinning a rocm cell because its flat
`DEFAULT_MAX_WAIT = 60` min bound cannot fit a cold ROCm build, and reopen/re-trigger cycles re-fired
the full matrix even when the cells were already published.

Measured on 2026-11-17 (asimov-agent/llgenie):

- producer run **44143247189** (head `8332018901`, #2840 rocm cell): job start 18:24:26Z, still
  `in_progress` at 19:25Z — **61+ min with nothing queued ahead** — > the 60-min bound, so the trigger
  expired and the reopen re-dispatched.
- engine-build-pr-trigger: **6 runs** (14:00–19:25Z) for 4 open engine PRs: 5 completed/failure, 1
  in_progress past 3 h. Failed trigger runs: 44122524444, 44125367352, 44125654443, 44125767180, 44141611556.
- 28 producer dispatches for ~15 distinct cells across reopen cycles; 9 dispatches cancelled, each
  re-queued at the back of the `engine-build-push` FIFO.

## The fix (scripts/engine_build_trigger.py)

1. **Published-skip** — `_published()` composes the merged may-arm's authority instead of opening a
   second registry read path: `check_engine_pins_published.exact_tags(engine, variant)` for the exact
   tag, `engine_image._digest_http(REGISTRY/<tag>)` for the manifest. A published cell prints
   `published-skip` and is never dispatched; when every cell skipped, the pass is green with zero
   dispatches. `dry` never probes.
2. **Per-arch budget** — `WAIT_MIN_BY_ARCH = {"rocm": 150}` over `DEFAULT_MAX_WAIT = 60`;
   `_wait_budget()` picks the class bound, an explicit `--wait-min` overrides every class.
3. **Replacement cap** — a `cancelled`/`skipped` producer costs **at most one** replacement dispatch
   per cell per trigger run, awaited on the carried budget `budget * REPLACEMENT_FACTOR(2) - consumed`,
   floor `REPLACEMENT_MIN_WAIT(10)`; a `guard_refused` outcome (policy refusal) is never replaced.

Cross-module edge `engine_build_trigger → engine_image` registered in `scripts/package-layers.json`.

## Decisions

- The probe reuses the may-arm's exact-tag/digest seam (one authority, no divergent registry reads).
- `check()` gained keyword-only test seams (`digest=`, `gh=`); `gh` moved keyword-only because `gh` is
  not a URL (the probe's "registry" is the GHCR org/repo prefix from `engine_image.REGISTRY`).
- Test chef models each dispatch as its own run id (77, 78, …) so the replacement's discovery loop
  never models a real GitHub dispatch as "no run appeared", and no test sleeps.

## Current status

OpenSpec change `trigger-wait-budget-2892` validated; 29/29 tests green
(`~/llama-gguf-tools/.venv/bin/python3 -m pytest tests/test_engine_build_trigger.py -q`, 8 new cases);
wiring + package-layers green. The companion ROCm layer-cache-export issue (cut cold-build time under
60 min) is filed separately — this lane makes the trigger tolerate what the cache work will shrink.

Issue: #2892
