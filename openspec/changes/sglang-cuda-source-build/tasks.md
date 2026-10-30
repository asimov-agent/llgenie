# Tasks — sglang-cuda-source-build

- [x] 1. `skills/engines/sglang/SKILL.md`: `install.cuda` clones the pinned sha, preinstalls torch 2.14.1 from the cu130 index, `pip install --no-build-isolation -e 'python[all]'`, and compiles the AOT CUDA kernels with `CMAKE_ARGS='-DCMAKE_CUDA_ARCHITECTURES={cuda_arch}'`; `container.cuda` drops `prebuilt: true` and adds `apt: [rustc-1.91, cargo-1.91, python3-dev, wget]`.
- [x] 2. `make generate-engine-params ENGINE=sglang`; the regenerated `containers/engines/params/sglang.json` + `containers/engines/dockerfiles/sglang/Dockerfile.cuda` are committed.
- [x] 3. `tests/test_engine_source_guard.py`: the census moves to 23 source / 8 prebuilt on this branch (vllm stays prebuilt – that is #937).
- [x] 4. `tests/test_engine_skills.py::test_official_upstream_images_are_used_as_bases`: sglang/cuda now compiles on the shared base, never FROM `lmsysorg/sglang`.
- [x] 5. `make check-engine-source`, `make check-engine-params`, `make check-engine-coverage` are green; affected tests pass.
- [x] 6. Per-cell build + detect service verified on the CI `engine-image-sglang-cuda` job (`make build-engine ENGINE=sglang ARCH=cuda` then `make test-engine-stage TEST=detect`); this lane never builds an engine image locally, it pulls and verifies the published artifact (skill rule).
- [x] 7. `make test-unit` green (full hermetic suite).
- [x] 8. `README.md` + `docs/ENGINES.md` "prebuilt cells" passage updated (sglang/cuda now a source build).
- [x] 9. `agent-wiki/2026-10-30-sglang-cuda-source-build.md`, `CHANGES.md` row (+ `docs/changes.d/`), OpenSpec `tasks.md` all ticked.
- [x] 10. `make openspec-validate NAME=sglang-cuda-source-build` exits 0.
