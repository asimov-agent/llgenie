# Tasks

- [x] 1. Write the proposal + spec for the smoke's model fetch (issue #385).
- [x] 2. `scripts/hf_download.py`: a throttle-aware pause (`Retry after N seconds` / `429` from the
      CLI's own output, capped) on top of the existing bounded retry budget.
- [x] 3. `scripts/hf_download.py`: a whole-repo snapshot target (`-` as the filename), with the
      fast path not mistaking the fresh destination for a completed download.
- [x] 4. `scripts/engine_smoke.py::fetch_model`: run `scripts/hf_download.py` instead of its own
      `hf download`.
- [x] 5. `tests/test_hf_download_retry.py`: a fake `hf` CLI that throttles once then succeeds
      (the wait is proven by the sleep), one that throttles forever (bounded, loud failure), and
      the snapshot fetch (fresh + already-present).
- [x] 6. `tests/test_engine_smoke_fetch.py`: `fetch_model` runs the one downloader (its argv names
      `scripts/hf_download.py`), and no bare `hf download` is left in the smoke.
- [x] 7. Wire the new test file into the test recipes; document the smoke's download path in the
      README and record the change in `agent-wiki/`.
- [x] 8. Verify: `make test-unit` green, `make lint`, `make check-wiring`, and
      `make openspec-validate NAME=engine-smoke-throttle` valid.
- [x] 9. Commit, push the branch, open the PR against upstream `main` (`closes #385`).
