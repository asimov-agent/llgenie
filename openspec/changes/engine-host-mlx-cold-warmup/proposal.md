# engine-host-mlx-cold-warmup — give the cold-model first /v1/chat/completions the full warm-up window

## Why

Main-head engine-build run `42318302931` (`workflow_dispatch`, head `faef07fa`) — cell
`engine-build-mlx-cpu` (job `128236450093`) — FAILED at the final host-verify leg: the published
`mlx:93e6d4a6-f7468b60-cpu` image pulled and served **READY**, but the assert `/v1/chat/completions`
to `127.0.0.1:11434` timed out (`TimeoutError: timed out` in `scripts/engine_host_test.py _chat`).
`serve_published` capped the first request at `min(timeout, 120)`, so a 900s configured warm-up was
silently cut to 120s. Some engines (mlx-cpu) load the model lazily on the **first** prompt — a
health-READY / first-token-timeout split is a cold-start artifact, not a serving bug. The first
request never got the window it needed to load and answer.

## What changes

`scripts/engine_host_test.py`:

- `serve_published` passes the **full** configured window to `_chat` (no more `min(timeout, 120)`
  pre-cap at the call site).
- `_chat` gives attempt 0 that full window (a lazy-load engine is retried on the now-warm vertex);
  retries drop to the conversation-norm `_CHAT_RETRY_CAP_S = 120`, so a genuine hang stays
  time-bounded (bounded attempts, small sleep) and still fails loudly.

Three hermetic tests (`test_serve_published_passes_the_full_warmup_window_to_chat`,
`test_chat_first_attempt_gets_the_cold_model_warmup_budget`,
`test_chat_budget_narrows_on_caller_timeout_below_the_cap`) lock the budget rule and
mutation-prove it (FAIL on base `faef07fa`, PASS on the fix head). No gate weakened; a true
serving bug still fails.

## Out of scope

- The sglang-cuda `no space left on device` build failure in the same run — separate defect
  (#1893, separate PR).
- Any vllm / engine-pin / ci-verdict class (distinct trackers).
- The mlx engine's own serving internals (option (c) was excluded by measurement: pull + READY
  were clean, so this is a harness timeout-policy defect, option (a)).

## Who

ci-pipelines-maintainer (this lane owns the harness/host-verify timeout policy, not the engine).
