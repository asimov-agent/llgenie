# Tasks

- [x] 1. `scripts/model_engine_pick.py::download` passes an explicit `timeout=DOWNLOAD_TIMEOUT` (default 3600 s, `LLGENIE_DOWNLOAD_TIMEOUT` overrides) to the `hf_download.py` child and the docstring states the derivation (~2x the child's own retry ladder)
- [x] 2. A `subprocess.TimeoutExpired` there raises `SystemExit` naming the repo/file, the seconds exceeded and the full command — never an empty result
- [x] 3. `scripts/hf_auth.py::hub_open` bounds its 429 sleeps by `RATE_LIMIT_TOTAL_BUDGET` (default 60 s, `HUB_RATE_LIMIT_BUDGET` overrides) as well as the existing `RATE_LIMIT_WAITS` count, and a wait that does not fit raises instead of sleeping
- [x] 4. The raised 429 keeps the Hub's status/headers and its message states the attempts spent, the waits spent, the seconds slept and the budget
- [x] 5. `tests/test_hf_auth.py`: a capped 600 s window fails before sleeping; the ceiling is a total (40 of 60, never 80); the message names the attempts, the waits and the budget
- [x] 6. `tests/test_model_engine_pick.py`: the child receives `timeout=DOWNLOAD_TIMEOUT`, and a real `hf` CLI that never returns is killed at a 2 s ceiling with a message naming `hf_download.py`
- [x] 7. Falsified: with `scripts/hf_auth.py` and `scripts/model_engine_pick.py` reverted to `HEAD`, the four bound tests fail (`slept == []` holds no longer; `'timeout' in kwargs` is False); restored, all 38 affected tests pass in `llgenie/test:latest`
- [x] 8. `agent-wiki/2026-10-29-bound-unit-network-waits.md` records the work with the issue and the PR, and `CHANGES.md` indexes it
- [x] 9. Gates green: `make test-unit`, `make lint`, `make check-docs`, `make check-wiring`, `make check-workflows`, `make check-pr-hygiene`, `make check-pr-authors`, `make openspec-tasks-check`, `make openspec-validate NAME=bound-unit-network-waits`
