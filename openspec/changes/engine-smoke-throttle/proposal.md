# The engine smoke's tiny model goes through the one downloader

## Why

An `engine-image-*` job can be red on a **Hub throttle** while the engine itself is fine
(issue #385). Measured on PR #374 and PR #372 (runs 39265327980 / 39265324103):

```
[smoke] $ hf download mlx-community/Qwen2.5-0.5B-Instruct-bf16 --local-dir /home/runner/models/smoke/...
Error: Local entry not found.
429 Too Many Requests: you have reached your 'api' rate limit.
Retry after 202 seconds (0/1000 requests remaining in current 300s window).
make[1]: *** [Makefile:762: test-engine] Error 1
```

The engine built. Its image was fine. `scripts/engine_smoke.py::fetch_model` calls the `hf` CLI
directly with `check=True`, so the Hub's throttle is fatal on its first answer — and the CI
matrix runs ~20 engine jobs in parallel that share one `HF_TOKEN`, spending the
1000-requests/5-minute window inside the run. The repository already has ONE downloader with a
stall-watch and an auto-resume/retry loop (`scripts/hf_download.py`), and the health check's model
fetch already routes through it (`scripts/download_test_model.py`); the engine smoke is the one
call site that does not.

## What Changes

- **`scripts/engine_smoke.py::fetch_model`** fetches its tiny model by running
  `scripts/hf_download.py` — the same single download path CI and the host use — instead of its
  own `hf download`. No second downloader, and no bare `hf download` left in the file.
- **`scripts/hf_download.py`** learns two things the smoke needs:
  - a **whole-repo snapshot** target (no single filename: `-` in place of the filename), so a
    safetensors/MLX model is fetched by the same downloader the GGUF path uses;
  - a **throttle-aware pause**: when an attempt fails and the CLI's own output names a Hub
    throttle (`429 Too Many Requests`, `Retry after N seconds`), the loop waits those seconds
    (capped) before the next attempt instead of the fixed short pause — the Hub's number, not a
    guess, and still on the existing bounded retry budget.
- **Tests**: a fake `hf` CLI (a real external system stand-in on `PATH`, no mocking of the
  product) that throttles once and then succeeds proves the wait and the retry; one that throttles
  forever proves bounded, loud failure; and `fetch_model` is proven to build its fetch through the
  one downloader.

## Impact

- The engine images' smoke stage stops turning an upstream throttle into an engine defect; the
  job waits the window out and then serves its tiny model.
- The GGUF download path keeps its behaviour (same fast path, same resume, same stall-watch); the
  snapshot mode is additive and used by the smoke only.
- Not here: the shared Hub GET seam's own 5xx/429 budget and its three duplicated implementations
  (`scripts/hf_auth.hub_open`, `model_engine_pick._hub_json`, `llgenie_serve._hf_get`) — that is
  issue #339.
