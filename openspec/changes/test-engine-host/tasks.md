# Tasks — test-engine-host

- [x] 1. `make test-engine-host` exists (a real `.PHONY` target) and calls
  `scripts/engine_host_test.py`; it reads the engine list and per-engine tuning from the committed
  params (`containers/engines/params/*.json`), never a hard-coded roster.
- [x] 2. The command is parameterized `ENGINE=<id> ARCH=<arch> MODEL=<model>` (owner refinement
  #1322): ARCH selects the specific arch-type cell and MODEL the LLM model to serve with; when
  omitted, the engine's smallest supported model (the repository's single smallest-model-per-format
  table) is served.
- [x] 3. Filtering to the host-supported arch set reuses `nvidia_compute_caps()` /
  `rocm_gfx_targets()` in `scripts/engine_skills.py` (cpu always; vulkan where a GPU render node
  exists); the host path serves ONE engine at a time (sequential, never parallel — GPU contention).
- [x] 4. Per engine the command serves the PUBLISHED image (pull AS-PUBLISHED via
  `engine_image.pull_published`, never builds a local image), asserts an llm-local
  `/v1/chat/completions` answer, and reports the measured t/s a real run produced
  (`timings.prompt_per_second` / `predicted_per_second` or the engine's own t/s usage field). A
  transient Hub 503 during the model fetch is retried with backoff, never aborting the run.
- [x] 5. The max-perf input per engine is READ from the generated params
  (`variants.<arch>.launch`/`env` via `engine_image.resolve`), never a hard-coded second copy.
- [x] 6. The engine-build workflow's LAST step runs the same parameterized `make test-engine-host`
  as a PARALLEL matrix over the supported (engine × arch) cells (one element per cell, max-parallel)
  keyed off the RUNNER's arch types at runtime; a GPU-less runner skips the GPU legs with a
  documented reason (issue #1240) and never reddens them.
- [x] 7. `make check-wiring` still passes (the script is wired to `test-engine-host`, which CI and
  the host reach); the host-only-wiring position is real calling, not roster silence; manifest
  assertions use subset checks (`expected <= set(actual)`).
- [x] 8. `make openspec-validate NAME=test-engine-host` exits 0 and the change record +
  `CHANGES.md` + `docs/changes.d/` + agent-wiki pages are committed.
