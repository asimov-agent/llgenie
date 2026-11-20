# Tasks: download-test-model-cache

- [x] 1. `Makefile` Linux branch: `MODEL_CACHE_RUN` (uid-mapped container, checkout mounted at its own path, `-e HOME=$(CI_HOME)`) and models-keeping `CI_HOME_CLEAN`
- [x] 2. `Makefile` Darwin branch: `MODEL_CACHE_RUN` (`env HOME=$(CI_HOME)` native run) and models-keeping `CI_HOME_CLEAN`
- [x] 3. `mk/tests.mk` `download-test-model`: `mkdir -p $(CI_HOME)` + run via `MODEL_CACHE_RUN`; docstring names the real destination
- [x] 4. New `tests/test_health_model_cache.py` pinning the macros, the recipe shape, the clean shape, and the loop download stage (targeted battery 68/68 incl. macos + split pins)
- [x] 5. Live proof: real `make download-test-model` run landed `.ci-home/models/Qwen/8GB/qwen2.5-0.5b-instruct-q4_0.gguf` (428,730,208 B, owner asimov) on the host; second run printed `already present` rc=0
- [x] 6. Live proof: `CI_HOME_CLEAN` invoked verbatim via `make --eval` removed `.ci-home/bin`, `.ci-home/.cache` and a seeded scratch file, kept `models` intact
- [x] 7. `make openspec-validate NAME=download-test-model-cache` exits 0
- [x] 8. `make test-unit` green on the lane; docs mirrored (agent-wiki entry + changes.d fragment)
- [x] 9. `make lane-preflight` prints `preflight: OK`
- [x] 10. (preflight verdict precedes this checkbox-only amend; push + PR follow this commit) Commit text mirrors the issue AC block; push + PR with closing keyword and mirrored AC block
