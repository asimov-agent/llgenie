# 2026-10-26 — the link check asks the Hub's API, and a 429 is not a dead link

Implements issue #690 (PR #691, OpenSpec change `registry-link-check-hub`).

## What was wrong (measured)

`make check-registry` is the weekly `registry-sync` job's first gate. In a throwaway detached worktree
at `8cbcf19`, in the job's own order:

```
make sync-registry            # OK: 23 models (2026-10-13T14:31:40Z) -> 106 models (2026-10-26T14:06:43Z)
make check-registry           # exit 1: 18 "dead README links", every one HTTP 429 Too Many Requests
```

The same URL back to back: `200` without the token, `429` with it ("we had to rate limit your IP …
make sure you pass a HF_TOKEN"). `check_links` was calling `hf_auth.authorize()` on a **Hub web page**,
so the check sent `Authorization: Bearer <HF_TOKEN>` to the model's HTML page, and the Hub answers a
token-bearing web-page GET from its API rate limit. The link the check called dead was dead only because
of how the check asked. Two aggravations: a 429 was definitive (`e.code < 500` → dead at once), and the
store now carries 90 unique README links (64 Hub model pages) versus the 15 of #435 — which filed this
class and was closed NOT_PLANNED.

CI passed the step (run 40402053825: `[check-registry] OK … models=106; README order matches, links
answer`), so the failure was local — and it is the gate that has to run locally to work on the store's
real blockers (#677/#687).

## What was decided

- **Ask the Hub's API for a Hub model.** `https://huggingface.co/<org>/<repo>` is checked as
  `https://huggingface.co/api/models/<org>/<repo>`: the same question (does the model exist), on the
  endpoint the token authenticates. Measured: 64/64 answer `200` in 9.8s.
- **One request policy.** `check_links` no longer builds its own ladder; every link goes through
  `hf_auth.hub_open` — a 429 waits `rate_limit_wait`, a 5xx/transport failure retries on the stated
  ladder, a 401/403/404 is definitive on the first attempt.
- **The token never reaches a page.** `hf_auth.authorize` attaches it on Hub *endpoints* (`/api/…`,
  `…/resolve/…`) only. Every caller in the repo (`hf_download`, `llgenie_serve`, `model_engine_pick`,
  `gen_trending_quant_catalog`) already targets those, so nothing else changed behaviour.

## Verified

- Red first: the three new tests fail on `origin/main`'s `sync_registry.py`/`hf_auth.py`
  (`3 failed`) and pass with the change (`6 passed` in `tests/test_trend_pick.py -k "link or authorize"`).
- `make check-registry` on the committed 23-model store: OK.
- `make check-registry` on a freshly synced 106-model store in a throwaway worktree (after
  `sync-quant-catalog`, `render-trend-list-matrix`, `render-engine-skill-gap`): `OK … 106 models; README
  order matches, links answer`, in 22.7s — the 18×429 run is gone.
- `make test-unit` and `make openspec-validate NAME=registry-link-check-hub` recorded in `tasks.md`.

## Status

Implementation complete on `feat/registry-link-hub-api` (PR #691). Deferred, each its own linked issue: the 101
data-pinned tests that still red `test-unit` on the 2026-10-26 store (#677, #687), the 16 engines with
no skill or dated decision (#673), and the `vram_tier`/list-order semantics (#669).
