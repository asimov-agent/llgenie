# Tasks — vllm-cuda-wheel

- [x] 1. `skills/engines/vllm/SKILL.md`: `container.cuda` → `base: docker.io/vllm/vllm-openai:v0.33.0` +
      `prebuilt: true` + `binary: "vllm"`; `install.cuda` cleared (0 steps). Mirror the rocm thin
      treatment (#2274). `install.rocm`/`install.cpu` unchanged.
- [x] 2. `make generate-engine-params ENGINE=vllm`; commit the regenerated
      `containers/engines/params/vllm.json` and `containers/engines/dockerfiles/vllm/Dockerfile.cuda`
      (now thin `FROM docker.io/vllm/vllm-openai:v0.33.0`, `prebuilt=true`, `install=[]`).
- [x] 3. `scripts/engine_source_guard.py`: vllm/cuda is `prebuilt: true` (thin image over vLLM's
      official CUDA serving base), so `findings()` skips it (guard line `if row["prebuilt"]: continue`)
      and `make check-engine-source` stays green with NO `KNOWN_NOT_SOURCE` entry — the old wheel/
      base-cuda entry was removed.
- [x] 4. `tests/test_engine_skills.py`: hermetic test that the cuda cell is thin/prebuilt with no
      source step and no install chain; a regression back to `-e .`/`build_rust.sh`/wheel reds.
- [x] 5. `make check-engine-params` green (0 stale, 0 drift); `make check-docs` green (change->note).
- [x] 6. PR open (`fix(engines)` on canonical asimov-agent/llgenie, body ends `closes #2386`);
      PR #2429 on branch `llgenie-engines-vllm-cuda-wheel`.
- [x] 7. CI engine-image-vllm-cuda cell green (engine-build dispatch run 42630517612, head e8774758,
      `make build-engine ENGINE=vllm ARCH=cuda` success + verify detect success).
- [x] 8. `agent-wiki/2026-11-09-vllm-cuda-wheel.md` + `docs/changes.d/` row + regenerated
      `CHANGES.md`; `make openspec-validate NAME=vllm-cuda-wheel` exits 0.
