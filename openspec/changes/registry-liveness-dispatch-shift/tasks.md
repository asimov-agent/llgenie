# tasks — registry-liveness-dispatch-shift

- [x] The dispatch loop in `.github/workflows/registry-liveness.yml` reads
      `sel engine variant tag extra` and accepts only contract-exact lines
- [x] A violating line prints `UNRECOGNIZED select line`, dispatches nothing, and fails the
      step via a post-loop `bad_line` check
- [x] A test in `tests/test_check_engine_pins_published.py` locks the workflow read fields to
      the four-token contract (proven locally: parsing main `e6b9b4b4f`'s yml yields fields
      `engine variant tag` — the test's assert fails on the old loop and passes on the fix;
      15/16 module tests pass, the 16th is the known live-registry backlog test)
- [x] `make check-engine-pins-published ALL=1`'s real `[select]` lines parse to committed
      engine ids (dots intact), valid variants, tag suffixes — proven locally: 19/19 cells
      dispatched `engine=<dotted id> arch=<variant> push=true` with zero shifted fields; a
      malformed-line run exited 1 with 4 `UNRECOGNIZED` reports and no malformed dispatch
- [x] `make openspec-validate NAME=registry-liveness-dispatch-shift` exits 0
- [x] All lane gates (`lint`, `check-workflows`, `check-wiring`, `check-docs`,
      `check-pr-hygiene`, `openspec-tasks-check`) are green at the fixing head.
