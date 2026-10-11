## Why

[Run 38178191656](https://github.com/asimov-agent/llgenie/actions/runs/38178191656) on `main` failed `linux / unit` and `macos / top-tier` with HTTP 429 from the Hugging Face Hub. `HF_TOKEN` was set. A free token is a fixed window of 1000 API requests per 5 minutes ([Hub rate limits](https://huggingface.co/docs/hub/en/rate-limits)), and the Hub reports the seconds left in that window as `RateLimit: "api";r=0;t=<seconds>`. It does not send `Retry-After`.

`_hf_get` retries a 429 after 1, 2, then 4 seconds. `_hub_json` caps its wait at 60 seconds. Both give up while the window is still closed. Retrying on a 1/3/5/7 minute ladder before the window resets spends the next window's budget on more 429s, and a counter that is not reset by a success treats the next blip as a continuation of the last one.

## What Changes

- `scripts/hf_auth.py` owns the wait: the `t` value from the `RateLimit` header, or 300 seconds when that value is absent, never more than 600 seconds. Every Hub caller and every test that drives a Hub 429 uses this function. No caller keeps its own 429 pause.
- A 429 may be retried twice. A response that is not a 429 resets that count, so the next 429 starts again at zero.
- 5xx and transport errors keep a short backoff with the same attempt budget. 401/403/404 still fail on the first try.
- Both `_hf_get` and `_hub_json` use this wait. A 429 that is still a 429 after the budget fails the call.
- `hub_open` in the same module is the GET every Hub download uses: the size lookup, the ranged chunk download and the preflight probe. A caller does not open a Hub URL itself.

## Impact

- `scripts/hf_auth.py`, `scripts/llama_serve.py`, `scripts/model_engine_pick.py`
- `tests/test_hf_auth.py`, `tests/test_llama_ai.py`, `tests/test_trend_pick.py`
- `README.md`
