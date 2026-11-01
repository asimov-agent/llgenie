# `make test-engine-host` parameterized: ENGINE/ARCH/MODEL, a parallel CI matrix, sequential host (issue #1322 refinement)

PR #1326 landed the host-side serve command (`make test-engine-host`) for #1322. The owner then
refined the mechanics (issue comment 6557944883, re-opened body): the command must be **parameterized**
`ENGINE=<id> ARCH=<arch> MODEL=<model>`, the engine-build pipeline's **end must be a PARALLEL matrix**
over the supported (engine × arch) cells, and the **host use is sequential one engine at a time**.
This change closes that refinement.

## What changed

1. **`MODEL=` parameterization.** `make test-engine-host ENGINE=<id> ARCH=<arch> MODEL=<model>` now
   serves ONE engine's published image against exactly that MODEL (threaded unchanged into
   `serve_published`). When `MODEL` is omitted the engine's smallest supported model (the repository's
   single smallest-model-per-format table) is served. The make target passes `--model`; the script's
   `--arch` filter and `--model` argument select what is served.
2. **Parallel CI matrix on the runner's arch types.** The engine-build workflow's LAST step
   (`host-verify MATRIX`) now runs the same parameterized command as a matrix over the supported
   (engine × arch) cells IN PARALLEL (one matrix element per cell, max-parallel 20), keyed off the
   arch types the GitHub Actions runner itself supports at runtime (the command reuses
   `engine_skills.nvidia_compute_caps()`/`rocm_gfx_targets()`, never the dev host's arch). A GPU-less
   runner skips the GPU legs with the documented #1240 reason and never reddens.
3. **Sequential host.** The lane drives the same command one engine at a time — never parallel on the
   host (engines contend for the GPU). `MODEL` is threaded through.
4. **Retry of a transient Hub 503/5xx** on the smallest-model fetch (with backoff), so a Hub blip
   during a full host sweep never aborts the run; only a permanent failure exits non-zero.

## Verification

- `tests/test_engine_host.py` (10 passed): arch grid, t/s reader, subset engine list, loud failure,
  the `MODEL`-selects-what-is-served path, and the 503-retry + permanent-failure-exit paths.
- `tests/test_engine_build_workflow.py` (11 passed): the parameterized last matrix step is truly
  last, passes ENGINE/ARCH/MODEL, and the target is `.PHONY` and never builds.
- `make check-wiring check-docs check-engine-params` green; `make openspec-validate
  NAME=test-engine-host` valid.
- Real host serve: `make test-engine-host ENGINE=llama.cpp ARCH=cpu|cuda MODEL=<model>` pulled the
  published image, answered llm-local and reported measured t/s on a real card.
