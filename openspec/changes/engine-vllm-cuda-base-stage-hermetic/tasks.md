# Tasks

- [x] Add `test_combine_base_stage_removes_cross_invocation_base_pull` sweeping every real derived engine Dockerfile (no bare base `FROM`, no `docker.io`, one `AS llgenie-base`).
- [x] Add `test_vllm_cuda_dockerfile_base_stage_is_hermetic` pinning the vllm cuda cell to the internal-stage form.
- [x] `tests/test_engine_image_matrix.py` full file green in the `llgenie/test` container (23 passed).
- [x] Docs trio per #1123: `agent-wiki/` note + `docs/changes.d/` fragment + `CHANGES.md` regenerated.
- [x] PR opens `closes #1832`; normal review flow (#1644 acceptance write-back, owner merges).
