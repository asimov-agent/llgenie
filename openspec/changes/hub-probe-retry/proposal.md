# hub-probe-retry — proposal

Issue: [#256](https://github.com/asimov-agent/llgenie/issues/256)

## Why

`tests/test_pick_full_registry.py::test_pick_matrix_real_quant_links_exist` reddens `main` on a transient
upstream, and the failure it prints cannot be told apart from a hallucinated link. Measured on `main`:

| run | commit | lane | result |
|---|---|---|---|
| [38850303216](https://github.com/asimov-agent/llgenie/actions/runs/38850303216) | `ed75b87` | `macos / unit` | **3 failed**, 4641 passed — `Qwen/Qwen3-14B-GGUF/resolve/main/Qwen3-14B-Q8_0.gguf` |
| [38855700095](https://github.com/asimov-agent/llgenie/actions/runs/38855700095) | `e02b542` | `macos / unit` | **1 failed**, 4654 passed — `lmstudio-community/Qwen3.8-27B-MLX-5bit/resolve/main/preprocessor_config.json` |

Both files exist. Replaying the probe's exact request from the maintainer host (`GET`, `Range: bytes=0-0`,
`User-Agent: llgenie-test`) answers **200** (307 → CDN 200), and both files are listed in their repo's
`siblings`. `linux / unit` is green on both commits with the same test file in its list — 2 of the last 7
completed `main` CI runs are red on this single test.

The probe is a one-shot: 20 s timeout, **no retry**, and every failure mode
(`HTTPError`, `URLError`, `TimeoutError`, `OSError`) collapses to `False`, so the assertion reports

```
AssertionError: qwen3.8-27b/mlx on cuda: real file missing (HTTP): https://huggingface.co/.../preprocessor_config.json
```

— identical wording for a 504, a 429, a stalled connection and a genuinely absent file. There are **two
copies** of it (`tests/test_pick_full_registry.py:346`, `tests/test_trending_quant_catalog.py:166`), which is
how they drifted from the retry budgets the product's Hub paths already carry
(`model_engine_pick._hub_json`: `2 ** (i + 1)`; `llama_serve._hf_get`). Issue #256's own thread measured the
same class on the product paths (22x500 + 11x504 in one run) and asks for a bounded retry budget plus a
legible cause.

## What Changes

- **One shared probe: `tests/hub_probe.py`.** A ranged `GET` with a bounded retry on the transient set —
  `429`, `500/502/503/504`, `URLError`, timeout, `OSError` — on the ladder `1, 2, 4, 8` seconds (5 attempts,
  ~15 s), returning a `Probe(exists, detail, attempts)`. `detail` keeps the **status**: `HTTP 206`,
  `HTTP 404`, `HTTP 503 after 5 attempts (15s of backoff)`, `URLError: <timed out>`. A definitive answer
  (404/403 and every other non-transient status) returns on the first attempt — a missing file stays a
  one-request failure.
- **A bounded outage budget.** Once `OUTAGE_LIMIT` probes in one process have exhausted the retry budget on
  a transient outcome, later probes take a single attempt and say so (`the Hub is in a degraded window`), so
  a sustained outage cannot multiply 15 s across the thousands of links these suites verify. It is a time
  bound, not a skip: the links stay unverified and the suite stays red, with the cause named.
- **Both copies deleted.** `test_pick_full_registry.py` and `test_trending_quant_catalog.py` call the shared
  probe and print its `detail` in the failure message.
- **The retry is locked by a real server.** New `tests/test_hub_probe.py` runs the real `urllib` client
  against a real loopback HTTP server: 206 -> exists in one request; 404 -> `False` with the status in one
  request (no retry); 503 then 206 -> exists, two requests; 503 forever -> `False` after exactly 5 requests
  with the ladder `[1, 2, 4, 8]` recorded; connection refused -> `False` naming the transport error; the
  breaker caps a later probe at one request.
- **Wired into the gate.** `tests/test_hub_probe.py` joins the `test-unit` list (it is the hermetic,
  deterministic proof; the live-Hub suites stay live).

## Not covered

- **`hf_auth.hub_open` does not retry 5xx at all** — the shared seam every Hub download goes through raises
  on the first `500/504`. That is product code and its own reviewed change: filed as
  [#339](https://github.com/asimov-agent/llgenie/issues/339), which links back here.
- **Collapsing the three product Hub-GET implementations into one helper** (#256's own "worth collapsing"
  note) — a fetch-layer refactor, out of this slice.
- [#254](https://github.com/asimov-agent/llgenie/issues/254) (the `macos-15-intel` queue) and the cancelled
  `main` runs the concurrency group drops — repo/runner settings, unchanged here.

Refs: [#122](https://github.com/asimov-agent/llgenie/issues/122) (the pick-matrix suite), #305/#306 (the
"a rule a substring satisfies" class this borrows its discipline from).
