# Tasks

- [x] 1. `test_offer_gives_strata_its_own_plan_and_llama_cpp_its_own` selects `strata` / `llama.cpp` by id, not index
- [x] 2. `test_interactive_pick_llama_cpp_for_the_same_model_gets_its_own_files` derives llama.cpp's position from the offer (`_engine_no`)
- [x] 3. Verified both tests address the engine by id on the old and new registry (llama.cpp = engine 2 / 3)
- [x] 4. `AGENTS.md` gains a durable rule: tests address engines by id, never by index
- [x] 5. `AGENTS.md` gains a durable rule: out-of-scope / `Not covered` work is filed as a separate linked issue, both ways
- [x] 6. The deferred ranking rule is filed as #225, linked from this PR's `Not covered` and from #223
- [x] 7. `make openspec-validate NAME=registry-sync-engine-identity` exits 0
