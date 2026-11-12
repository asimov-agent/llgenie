# Tasks — liveness-dispatch-coalescing (#2579)

- [x] `.github/workflows/registry-liveness.yml`: dispatch step validates `[select]` lines
      first, then dispatches ONE `push=true` sweep when count > 1 and the per-cell dispatch
      only when count == 1 (proven: patch applied; `test_the_dispatch_coalesces_a_multi_cell_wave_into_one_sweep` green)
- [x] New hermetic lock in `tests/test_check_engine_pins_published.py`: sweep shape (no
      engine/arch fields on the multi-cell call), single-cell shape intact, refusal fires
      before either path (proven: module 20/20 hermetic in the test container, rc=0)
- [x] Existing #2561/#2567/#2259 locks stay green unchanged (proven: same 20/20 run)
- [x] `make check-workflows` + `make check-wiring` rc=0 (proven: [workflows] OK,
      [check-wiring] OK 421 documents)
- [x] `make openspec-validate NAME=liveness-dispatch-coalescing` exits 0 (proven: rc=0,
      "Change 'liveness-dispatch-coalescing' is valid")
- [x] The stamped PR pair carries the gate-required `AGENTS:`/`BASE:` lines: `make
      bot-stamp-body` emits the pair and `make check-pr-agents-line PR_BODY=<stamped body>
      PR_BASE=origin/main` returns rc=0 (proven: stamped pair `AGENTS:
      1e7daa279655068e215e66ab505b4764d0228a99 94708b 1400l` + `BASE:`;
      `[check-pr-hygiene] OK: the AGENTS: line is reachable from both head and base`,
      rc=0). (PR CI-green / mergeStateStatus CLEAN / auto-merge-armed are standing loop
      duties tracked by `ci-verdict` + auto-merge, not a task this change can tick itself.)
