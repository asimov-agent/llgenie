# engine-smoke-documented-flags — tasks

- [x] 1. `scripts/engine_smoke.py` image path: probe `ei.variant_flags(spec)` behind the `probe:
      device` skip; vocabulary guard `{-h, --help, --version}` fail-closed naming engine+variant;
      empty flags → pinned `["-h", "--version"]` default. (verified: tests/test_engine_smoke_binary_flags.py
      scenarios 1–5 green, 25 passed rc=0 at the PR head)
- [x] 2. `scripts/engine_smoke.py` host skill path: probe `es.documented_flags(skill, backend)`
      selected from the plan's backend; same guard and default. (verified: per-backend-map +
      documented-nothing scenarios green in the same 25-pass run)
- [x] 3. New hermetic module `tests/test_engine_smoke_binary_flags.py`: per-variant probe sets
      (mlx-cpu `--help` only, llama.cpp both, empty → default), device skip preserved, vocabulary
      violation exits 1, per-backend map honored, plus the canary on the real committed manifest —
      monkeypatched manifest + captured subprocess, no docker, no engine builds. (verified: 8/8;
      with adjacent test_engine_binary_flags.py + test_engine_smoke_fetch.py 25 passed rc=0 hermetic TEST_RUN)
- [x] 4. `agent-wiki/2026-11-12-engine-smoke-documented-flags-2573.md` + `docs/changes.d/` entry;
      `make changes-index` re-rendered CHANGES.md; `make check-docs` passes. (verified: rc=0 at the PR head)
- [x] 5. Hermetic gates green at the PR head: pytest modules 25 passed rc=0,
      `make openspec-validate NAME=engine-smoke-documented-flags` rc=0, `make check-wiring` rc=0,
      `make lane-preflight` prints `preflight: OK`.
- [x] 6. `tests/test_engine_skills.py` text locks updated to the documented-flags shape
      (the old lock demanded the removed literal `flags = ["-h", "--version"]`): it now locks
      `DEFAULT_BINARY_FLAGS`, `DOCUMENTED_FLAG_VOCAB`, and `_documented_probe_set`.
      (verified: pytest `tests/test_engine_skills.py tests/test_engine_smoke_binary_flags.py` 110 passed rc=0 hermetic TEST_RUN, 2026-11-12)
