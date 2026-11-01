# Tasks — test-engine-host

- [x] 1. `make test-engine-host` exists (a real `.PHONY` target) and calls
  `scripts/engine_host_test.py`; it loads the engine list from the committed params
  (`containers/engines/params/*.json`), never a hard-coded roster.
- [x] 2. The command filters to engines the host's arch type supports (reuses
  `nvidia_compute_caps()` / `rocm_gfx_targets()` in `scripts/engine_skills.py`; cpu always;
  vulkan where a GPU render node exists) and serves ONE engine at a time (a serial loop).
- [x] 3. Per engine the command serves the PUBLISHED image (pull AS-PUBLISHED via
  `engine_image.pull_published`, never builds a local image), with the smallest supported model
  (the repository's single smallest-model-per-format table), asserts an llm-local
  `/v1/chat/completions` answer, and reports the measured t/s a real run produced
  (`timings.prompt_per_second` / `predicted_per_second` or the engine's own t/s usage field).
- [x] 4. The max-perf input per engine is READ from the generated params
  (`variants.<arch>.launch`/`env` via `engine_image.resolve`), never a hard-coded second copy.
- [x] 5. The engine-build workflow's LAST step runs the same `make test-engine-host` command on the
  CI runner (per engine x arch publish leg); a GPU-less runner skips the GPU legs with a documented
  reason (issue #1240) and never reddens them.
- [x] 6. `make check-wiring` still passes (the script is wired to `test-engine-host`, which CI and
  the host reach); the host-only-wiring position is real calling, not roster silence; manifest
  assertions use subset checks (`expected <= set(actual)`).
- [x] 7. `make openspec-validate NAME=test-engine-host` exits 0 and the change record +
  `CHANGES.md` + `docs/changes.d/` + agent-wiki pages are committed.
