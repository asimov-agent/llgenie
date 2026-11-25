# Tasks: trend-list-matrix-rerender-3056

- [x] 1. Cut `feat/trend-list-matrix-rerender` from the latest `origin/main` (measured at
      `e310a8739ec93e9ed648be0fc6b7e5646e964220`, the merge of #3052).
- [x] 2. Re-pull the live inputs in the fixed order: `make -s sync-registry` then
      `make -s sync-quant-catalog` (the trending build the matrix is rendered from). (proven: both rc=0
      at this head, `SYNC_REGISTRY_RC=0` / `SYNC_QUANT_RC=0`, the quant snapshot rewritten.)
- [x] 3. `make -s render-trend-list-matrix` writes the new
      `tests/fixtures/trend-list-matrix.json` + `tests/fixtures/hub-snapshot.json` pair, and
      `make -s check-trend-list-matrix` exits 0 on it. (proven: render rc=0 printing "wrote
      tests/fixtures/trend-list-matrix.json (81 cases) and tests/fixtures/hub-snapshot.json (103 Hub
      answers)"; the matrix gate rc=0 printing "OK tests/fixtures/trend-list-matrix.json (81 cases,
      recorded tests/fixtures/hub-snapshot.json)"; the matrix delta is 4 lines — the `metal/24/8`,
      `metal/24/32`, `metal/24/60`, `metal/24/64` cells, each "smallest GGUF is 6 GB > 10 GB this host
      can hold" -> "… is 10 GB …".)
- [x] 4. `make -s render-engine-skill-gap` then `make -s skills-validate` exit 0 on the new trending
      data (the rest of the post-merge step-5 order). (proven: gap rc=0 printing "wrote
      data/engine-skill-gap.json"; skills-validate rc=0 printing "18 skills, registry 18 engines,
      0 error(s)".)
- [x] 5. `make check-trend-list-fresh` exits 0 on the branch: the live read names no disagreeing cell,
      including the 4 `metal/24/*` cells issue #3056 lists. (proven: rc=0 printing "[trend-staleness]
      fresh: the fixture agrees with the live trending in all 81 cells (fingerprint 8b5bb053568fd9f1,
      registry 2026-11-17T08:25:02Z)" — the drift fingerprint `866ec6ad00f3` the issue was filed under
      is gone from the read.)
- [x] 6. `make openspec-validate NAME=trend-list-matrix-rerender-3056` exits 0. (proven: rc=0 printing
      "Change 'trend-list-matrix-rerender-3056' is valid".)
- [x] 7. `make test-unit` exits 0 on the branch with the hermetic matrix replay green
      (`tests/test_trend_list_matrix.py`): the whole battery, zero skipped. (proven at this lane's
      head — the tally is recorded in the PR's acceptance proof, and the same battery runs in the
      lane's `ci-unit` job.)
- [x] 8. The committed branch tree carries the lane's `agent-wiki/` note and its `docs/changes.d/`
      fragment. (proven: `make changes-index` rc=0 writing CHANGES.md from 966 fragments and
      `make check-docs` rc=0 with this lane's note and row in place.)
