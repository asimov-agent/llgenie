# Tasks

- [x] 1. `TOP_TIER_DRY_RUN_TIMEOUT` is `RATE_LIMIT_WAIT_CAP + 180` in `scripts/hf_auth.py`
- [x] 2. Both dry-run subprocesses in `tests/test_top_tier_acceptance.py` use that name
- [x] 3. Unit tests lock the 780-second sum, both call sites, and a real local-server 429
- [x] 4. README states the CI dry-run budget
- [x] 5. `make openspec-validate NAME=top-tier-dry-run-budget` exits 0
- [x] 6. Every other `llama_serve.py` or `hf_download.py` subprocess that can call the Hub uses that same budget. Local-file pickers stay short.
