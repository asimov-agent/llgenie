# Tasks: engine-selection-canonical

- [x] 1. `scripts/engine_image.py matrix()` hard-fails an explicit engine/arch selection that
      resolves to zero committed cells: named error (`no committed engine id '<x>'` /
      `'<engine>' has no committed variant '<arch>'`), CLI exit non-zero; placeholder row kept
      ONLY for unscoped (no engine, no arch) selections
- [x] 2. `scripts/check_engine_pins_published.py` emits `[select] <engine-id> <variant> <tag>`
      lines (committed ids, dots intact) for every unpublished cell in the ALL=1 sweep output
- [x] 3. `.github/workflows/registry-liveness.yml` dispatch step consumes only `[select]` lines
      (no engine id derived from package URLs; no-`[select]` red gate prints and exits 0)
- [x] 4. Tests: `llama-cpp` replay hard-fail; engine+bad-variant hard-fail; unscoped `--changed`
      placeholder preserved; scoped engine+variant exact-row; `[select]` lines carry dotted ids;
      dispatch step text builds inputs only from `[select]` lines
- [x] 5. Targeted pytest (matrix + pins + workflow tests) rc=0 — 9/9 new+updated tests, 47/48 in
      the two files (the 1 failure is the live `test_every_committed_engine_cell_tag_is_published_live`
      registry gap from `aa700cf27`, tracked by #2529 and its dispatch sweep, not this change),
      plus 250/250 in the consumer test files (`test_ci_variant_matrix`, `test_engine_build_workflow`,
      `test_engine_bump`, `test_engine_force_rebuild`, `test_engine_skills`, `test_mac_trend_pick`)
- [x] 6. Live contract proof on the red fleet tree: `make check-engine-pins-published ALL=1`
      printed 24 `[select]` lines including all 9 dotted cells (`[select] llama.cpp cpu
      7d7f0287-1b5db7a2-cpu` …); `make engine-build-matrix ENGINE=llama-cpp` exited non-zero
      naming `llama-cpp` ("no committed engine id"); `make engine-build-matrix ENGINE=llama.cpp
      ARCH=cpu` exited 0 with exactly `[{"engine": "llama.cpp", "variant": "cpu"}]`
- [x] 7. `make openspec-validate NAME=engine-selection-canonical` rc=0
- [x] 8. agent-wiki entry naming issue #2561 (and the PR it ships through)
- [x] 9. The PR staging is ready: a body carrying `closes #2561`, the acceptance criteria ticked
      on the proven-evidence stamps above, and the `AGENTS:`/`BASE:` pair from
      `make bot-stamp-body` (rc=0, `AGENTS: aa700cf2709485c4bc73778c3466405151e373dd 92544b 1373l`)
