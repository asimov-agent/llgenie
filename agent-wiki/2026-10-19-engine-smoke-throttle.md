# The engine smoke fetches its model through the one downloader (issue #385)

**Issue:** [#385](https://github.com/asimov-agent/llgenie/issues/385) · **PR:** (this branch) ·
**Change:** `openspec/changes/engine-smoke-throttle`

## What was wrong

`scripts/engine_smoke.py::fetch_model` called the `hf` CLI itself
(`subprocess.run(cmd, check=True)`), so the first Hub answer ended the job. Measured on
PR #374 (`chore/engine-bump-vllm`) and PR #372 (`chore/engine-bump-mlx`), runs 39265327980 /
39265324103:

```
429 Too Many Requests: you have reached your 'api' rate limit.
Retry after 202 seconds (0/1000 requests remaining in current 300s window).
make[1]: *** [Makefile:762: test-engine] Error 1
```

The engine built; its image was fine. The CI engine matrix runs ~20 jobs in parallel on one
`HF_TOKEN`, so the run spends the 1000-request/5-minute window itself and then reports the engine
as broken. `scripts/hf_download.py` is the repository's single download path (stall-watch,
auto-resume, bounded retry) and the health check's model fetch already used it.

## What changed

- `scripts/engine_smoke.py::fetch_model` runs `scripts/hf_download.py` (repo, filename-or-`-`, dest,
  label) — the same call shape `scripts/download_test_model.py` uses. No `hf download` call site is
  left in the smoke, proven by an AST guard in the test.
- `scripts/hf_download.py`:
  - **whole-repo snapshot** (`-` as the filename) so a safetensors/MLX model uses the same
    downloader; `_present()` ignores the destination's own progress log and dot-sidecars, so a
    freshly created (or already-downloaded) directory is never mistaken for a finished download;
  - **throttle-aware pause**: a failed attempt whose output names a Hub throttle waits the seconds
    the Hub printed (`hf_auth.throttle_wait`, capped at the same 10-minute ceiling
    `rate_limit_wait` uses), then retries on the existing bounded budget.
- Tests: `tests/test_hf_download_throttle.py` drives the REAL `hf_download.main()` against a real
  fake `hf` process (`tests/fixtures/fake_hf.py` gained `throttle-once`, `throttle-forever` and
  `snapshot` modes); `tests/test_engine_smoke_fetch.py` drives the real `fetch_model` and asserts
  the command it builds; `tests/test_hf_auth.py` covers `throttle_wait` (the Hub's number, the
  window/cap policy, text naming no throttle).

## Verified

- `pytest tests/test_hf_download_throttle.py tests/test_engine_smoke_fetch.py tests/test_hf_auth.py
  tests/test_hf_download_stall.py tests/test_hf_download_retry.py` — green in `llgenie/test`.
- The throttle test asserts the real 2-second wait the fake Hub names with a 0.1s retry pause, so a
  pass cannot come from the old fixed pause.

## Not covered

The shared Hub GET seam's own 5xx/429 budget and its three duplicated implementations
(`hf_auth.hub_open`, `model_engine_pick._hub_json`, `llgenie_serve._hf_get`) — issue #339.
