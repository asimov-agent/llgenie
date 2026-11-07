# 2026-11-07 — engine-host: cold-model first /v1/chat/completions gets the full warm-up window (issue #1894)

Issue: [#1894](https://github.com/asimov-agent/llgenie/issues/1894)
OpenSpec: `openspec/changes/engine-host-mlx-cold-warmup`
PR: [#1896](https://github.com/asimov-agent/llgenie/pull/1896)

## What changed

Main-head engine-build run `42318302931` (`workflow_dispatch`, head `faef07fa`) — cell
`engine-build-mlx-cpu` (job `128236450093`) — failed at the final host-verify leg: the published
`mlx:93e6d4a6-f7468b60-cpu` image pulled and served **READY**, but the assert `/v1/chat/completions`
to `127.0.0.1:11434` timed out (`TimeoutError: timed out` in `scripts/engine_host_test.py _chat`).

Root cause: `serve_published` capped the first request at `min(timeout, 120)`, so the configured
900s warm-up window was silently cut to 120s. Some engines (mlx-cpu) load the model lazily on the
**first** prompt — a health-READY / first-token-timeout split is a cold-start artifact (option (a)),
not a serving bug (pull + READY were clean, excluding option (c)).

The fix: `serve_published` passes the **full** configured window to `_chat`; `_chat` gives attempt 0
that window and caps retries at `_CHAT_RETRY_CAP_S = 120`, so a genuine hang stays time-bounded and
fails loudly. No gate weakened.

## Measured verification (this lane, at fix head `462bad98`)

- Three hermetic tests lock the budget rule (`test_serve_published_passes_the_full_warmup_window_to_chat`,
  `test_chat_first_attempt_gets_the_cold_model_warmup_budget`,
  `test_chat_budget_narrows_on_caller_timeout_below_the_cap`) — **mutation-proved**: the warm-up
  tests FAIL on base `faef07fa` (the pre-cap is present) and PASS on the fix head.
- `test_engine_host.py` 13 passed; py_compile green.

## Left open for the dispatcher

A green re-run of the mlx/cpu host-verify cell at the fix head is owned by the dispatcher lane
post-merge, with the answer + measured t/s + run id recorded as the remaining acceptance box on
#1894.
