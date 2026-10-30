# Tasks — vllm-source-build

- [x] 1. `skills/engines/vllm/SKILL.md`: drop `prebuilt: true`; `install.cuda` clones the pin and builds with `CMAKE_ARGS='-DCMAKE_CUDA_ARCHITECTURES={cuda_arch}' VLLM_TARGET_DEVICE=cuda uv pip install --no-build-isolation -e .`; `install.rocm` uses `PYTORCH_ROCM_ARCH='{gpu_targets}' VLLM_TARGET_DEVICE=rocm`; `install.cpu` uses `VLLM_TARGET_DEVICE=cpu`. `hw_flags` keys the fat arch lists. `container.{cuda,rocm,cpu}.apt` adds `python3-dev`.
- [x] 2. `make generate-engine-params ENGINE=vllm`; the regenerated `containers/engines/params/vllm.json` + `containers/engines/dockerfiles/vllm/Dockerfile.(cpu|cuda|rocm)` are committed.
- [x] 3. `tests/test_engine_source_guard.py`: the census moves to 25 source / 6 prebuilt on this branch (sglang/cuda stays prebuilt – that is #938).
- [x] 4. `tests/test_engine_skills.py::test_official_upstream_images_are_used_as_bases`: vllm's cells now compile on the shared base, never FROM `vllm/vllm-openai*`.
- [x] 5. Per-cell build + detect service verified on the CI `engine-image-vllm-<arch>` jobs (`make build-engine` then `make test-engine-stage TEST=detect|cpu`); this lane never builds an engine image locally, it pulls and verifies the published artifact (skill rule).
- [x] 6. `make check-engine-source`, `make check-engine-params`, `make check-engine-coverage`, `make test-unit` green.
- [x] 7. `README.md` + `docs/ENGINES.md` "prebuilt cells" passage updated to six on this branch (ollama ×4, tensorrt-llm/cuda, sglang/cuda) — vLLM's three are now source builds.
- [x] 8. `agent-wiki/2026-10-30-vllm-source-build.md`, `CHANGES.md` row (+ `docs/changes.d/`), OpenSpec `tasks.md` all ticked.
- [x] 9. `make openspec-validate NAME=vllm-source-build` exits 0.
