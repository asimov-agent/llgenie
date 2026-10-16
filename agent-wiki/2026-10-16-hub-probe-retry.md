# One live-Hub probe, with a bounded retry and a legible cause (#256)

## Why

`tests/test_pick_full_registry.py::test_pick_matrix_real_quant_links_exist` reddened `main` on a
transient upstream, and printed the same line a hallucinated link would:

```text
AssertionError: qwen3.8-27b/mlx on cuda: real file missing (HTTP): https://huggingface.co/.../preprocessor_config.json
```

Measured on `main` before this change:

| run | commit | lane | result |
|---|---|---|---|
| [38850303216](https://github.com/asimov-agent/llgenie/actions/runs/38850303216) | `ed75b87` | `macos / unit` | 3 failed, 4641 passed — `Qwen/Qwen3-14B-GGUF/.../Qwen3-14B-Q8_0.gguf` |
| [38855700095](https://github.com/asimov-agent/llgenie/actions/runs/38855700095) | `e02b542` | `macos / unit` | 1 failed, 4654 passed — `lmstudio-community/Qwen3.8-27B-MLX-5bit/.../preprocessor_config.json` |

Both files answer HTTP 200 to the probe's exact request from the maintainer host (307 → CDN 200) and both
are listed in their repo's `siblings`; `linux / unit` was green on both commits with the same test file in
its list. 2 of the last 7 completed `main` runs were red on this one test.

## What landed

- `tests/hub_probe.py` — the single probe: ranged GET, retries `429/500/502/503/504` and transport errors
  on the bounded ladder `1, 2, 4, 8` s (5 attempts), returns `Probe(exists, detail, attempts)` where
  `detail` is the status or the transport reason. A definitive status (404/403) returns on the first
  request and is never retried. After `OUTAGE_LIMIT` (3) exhausted probes the Hub counts as degraded and
  later probes take one attempt — a time bound, never a skip: the links stay unverified and the suite
  stays red.
- Both copies deleted (`test_pick_full_registry.py`, `test_trending_quant_catalog.py`): each calls the
  shared probe and prints its `detail`. `tests/test_hub_probe.py` fails if any `tests/*.py` defines
  `_url_exists` again.
- `tests/test_hub_probe.py` — 8 cases against a real loopback HTTP server (the real `urllib` client, the
  real `Request` the probe builds): 206 one request; 404 one request; 204 one request with its own attempt
  count; 503-then-206 two requests with one 1 s wait; 503-forever 5 requests with the ladder `[1, 2, 4, 8]`;
  connection refused reported as the transport error; the breaker capping a degraded probe at one request;
  the no-copy guard.

## Verification

Falsified on the real server (old code copied verbatim from `main`, each probe on its own fresh server):

```text
script=[503, 206]: OLD probe -> exists=False (1 request(s); 'real file missing (HTTP)')
script=[503, 206]: NEW probe -> exists=True  detail='HTTP 206' (2 attempts)
script=[503]:       OLD probe -> exists=False (1 request(s))
script=[503]:       NEW probe -> exists=False detail='HTTP 503 after 5 attempts (15s of backoff)'
```

- `tests/test_hub_probe.py`: **8 passed** in `llgenie/test:latest`.
- README's pick-matrix section names the shared probe, its retry budget and the breaker.
- Related: #339 (filed here) — `hf_auth.hub_open` still raises on the first Hub 5xx; that is product code,
  its own change.

Refs: #256 (the issue), #122 (the pick-matrix suite), #305/#306 (the "a rule a substring satisfies" class
this borrows its discipline from).
