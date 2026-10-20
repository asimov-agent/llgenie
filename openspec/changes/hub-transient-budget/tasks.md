# Tasks

- [x] 1. `scripts/hf_auth.py::hub_open`: retry the whole transient set (429, 5xx, transport) on a stated budget (`RATE_LIMIT_WAITS`, `HUB_MAX_ATTEMPTS`, `HUB_BASE_PAUSE`), raise on the first answer for every other status, and accept a pluggable `opener` transport
- [x] 2. `scripts/model_engine_pick.py`: `_hub_open` = IPv4 transport + the shared budget; `_hub_json` drops its own ladder (and its unused `attempts` parameter)
- [x] 3. `scripts/model_engine_pick.py::_tree`: a transient status is unknown, NOT a cached empty repo
- [x] 4. `tests/test_hub_transient_budget.py`: a real loopback Hub proving the budget by its own request count (503→200, eternal 503, definitive 404, eternal 429 with the waits recorded) and the pick stack on top of it (retry into a real tree; no poisoned cache)
- [x] 5. Wire the new file into the `test-unit` recipe; document the seam in the README and record the change in `agent-wiki/`
- [x] 6. Verify: the new file green, the four affected suites green (268 passed), `make lint`, `make check-docs`, `make check-wiring`, `make openspec-validate NAME=hub-transient-budget`
- [x] 7. Commit, push, open the PR against upstream `main` (references #339; does **not** close it — deduping `llgenie_serve._hf_get` remains), and comment on #339 with what landed
