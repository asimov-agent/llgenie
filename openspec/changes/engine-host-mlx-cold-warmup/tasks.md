# engine-host-mlx-cold-warmup — tasks

- [x] `serve_published` passes the full configured window to `_chat` (remove the `min(timeout,120)` pre-cap); `_chat` gives attempt 0 that window, retries cap at `_CHAT_RETRY_CAP_S=120` (issue #1894).
- [x] `test_serve_published_passes_the_full_warmup_window_to_chat` + `test_chat_first_attempt_gets_the_cold_model_warmup_budget` + `test_chat_budget_narrows_on_caller_timeout_below_the_cap`; mutation-proved (fail on base `faef07fa`, pass on fix head).
- [x] `test_engine_host.py` 13 passed; py_compile green.
- [x] Docs trio per #1123: `agent-wiki/` note + `docs/changes.d/` fragment; openspec spec + proposal + tasks.
