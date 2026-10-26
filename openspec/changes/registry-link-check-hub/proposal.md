# The link check asks the Hub's API, and never treats a throttle as a dead link

## Why

`make check-registry` is the weekly `registry-sync` job's first gate. Against a freshly synced store it
reds on the host with every Hub link "dead" (issue #690, measured on `8cbcf19` in a throwaway worktree
in the job's own order):

```
make sync-registry   # OK: 23 models (2026-10-13T14:31:40Z) -> 106 models (2026-10-26T14:06:43Z)
make check-registry  # exit 1
  https://huggingface.co/Qwen/Qwen3.5-0.8B -> HTTP Error 429: Too Many Requests
  ... 18 rows, all 429 ...
```

The same URL answers `200` **without** the token and `429` **with** it, measured back to back. The cause
is in `scripts/sync_registry.py::check_links`: it attaches the Hub token (`hf_auth.authorize`) to a
**Hub web page** (`/<org>/<repo>`), and the Hub answers a token-bearing web-page GET from its API rate
limit — "we had to rate limit your IP … make sure you pass a HF_TOKEN". The check's own auth header is
what makes the link read as dead. Two things make it worse: a 429 is classified as definitive
(`e.code < 500` → dead at once, never retried), and the store now carries **90 unique README links (64
Hub model pages)**, up from 15 when #435 filed the same class (closed NOT_PLANNED).

CI passes this step today (run 40402053825: `[check-registry] OK … models=106; README order matches,
links answer`), so the failure is a local one caused by how the check calls the Hub — and it is the gate
that has to be runnable locally to work on the store's real blockers (#677/#687).

## What changes

1. **A Hub model page is checked through the Hub's API.** `https://huggingface.co/<org>/<repo>` becomes
   `https://huggingface.co/api/models/<org>/<repo>`: same question (does this model exist), asked on the
   endpoint the token authenticates, with no HTML path to rate-limit. A 404 there is a dead link, named.
2. **Every link goes through the one Hub seam.** `check_links` no longer builds its own retry ladder; it
   calls `hf_auth.hub_open`, which waits out a 429 (`rate_limit_wait`), retries the 5xx and transport
   failures on its stated ladder, and raises a 401/403/404 on the first attempt. A non-Hub host gets no
   token (`_hub_host`) and the same policy.
3. **`hf_auth.authorize` stops attaching the token to a Hub web page.** It attaches only on the Hub
   *endpoints* (`/api/…`, `/<repo>/resolve/…`), which is where every caller in the repo already points
   (`hf_download`, `llgenie_serve`, `model_engine_pick`, `gen_trending_quant_catalog`). Measured: a
   token on the page is exactly what returns the 429.

The gate keeps its teeth: `check_registry.check` still fails on a link that does not answer and names
it, and `check_readme_matches` is untouched.

## Impact

- `scripts/sync_registry.py` — `check_links()` (API target for a Hub model page, `hf_auth.hub_open` for
  every link) and a `hub_api_url()` helper that answers `None` for anything that is not a Hub model page.
- `scripts/hf_auth.py` — `authorize()` attaches the token to Hub endpoints only, never to a Hub web page.
- `tests/test_trend_pick.py` — a hermetic test proving a Hub model page is asked at `/api/models/...`
  with the token and that a 429 is waited out (not reported dead) while a 404 is still reported dead on
  the first attempt; the live link test keeps passing unchanged, and the existing 504-then-200 test keeps
  its assertions with its sleep monkeypatch retargeted to the seam the ladder now lives in.

Verified: `make check-registry` exits 0 on the committed 23-model store and on a freshly synced
106-model store on this host; `make test-unit` green.

Not in this change: the 101 data-pinned tests that still red `test-unit` on the 2026-10-26 store (#677,
#687), the 16 engines with no skill or dated decision (#673), and the `vram_tier`/order semantics (#669).
