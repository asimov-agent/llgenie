# A gated Hub file is not a dead link

Issue #418. OpenSpec change: `catalog-gated-link`. PR: (this branch, opened against `asimov-agent/llgenie:main`).

## What was wrong

`registry-sync` (run `39240829581`) failed on:

```
FAIL: 1 newly-generated link(s) do not resolve (HTTP):
  https://huggingface.co/meta-models/Muse-Spark-Open-816B-A42B/resolve/main/chat_template.jinja
```

Measured 2026-10-20: the repo answers `200`, the file answers **`401`** — it exists, gated. `_probe_exists()`
counted only `200`/`206` as present, so 401/403 and 404 were the same answer and one gated model blocked the
whole weekly refresh. The repo already treats 401/403 as reachable in `make web-coverage`
(OpenSpec `agent-web-reach`).

## What changed

- `scripts/gen_trending_quant_catalog.py` — `_probe_status()` returns `ok` (200/206), `gated` (401/403) or
  `dead` (everything else); `_probe_exists()` keeps its meaning; the sync fails only on `dead` and prints
  `gated=N` plus the URLs.
- `tests/test_quant_generator_edges.py` — the seams move to `_probe_status`, plus the status classifier and
  a gated new link that no longer reds a sync.

## Verification

- `pytest tests/test_quant_generator_edges.py` → 9 passed.
- `make check-quant-catalog` (the committed table is untouched), `make check-docs`, `make check-wiring`,
  `make lint`, `make openspec-validate NAME=catalog-gated-link`, `make test-unit`.
- Negative control: the OLD module has no `_probe_status` and returns `False` on 401, so the new gated-link
  test fails against it (it asserts `rc == 0`).

## Honest limits

- The runner's `HF_TOKEN` authorization for `meta-models/*` is a repo setting; the probe is now right either
  way.
- The lossy store that also reds `registry-sync` is andyholst/trending-local-llms#463 — separate.
