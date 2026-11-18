# Proposal: post-merge live verification duty + trend-matrix re-pin (issue #2900)

## Why

`ci-hf-live`, the network battery that proves the repo's collected trend data matches live
HuggingFace trending, has failed on every recent main run. Measured on main
`7720d5bb98dc440f00d595004dcf63cd3d6e2d50`: run `44212692903` (schedule, 2026-11-18) ended
`4 failed, 13468 passed` — `test_trend_list_matches_the_committed_matrix[metal/16/8|32|60|64]`;
the committed fixture pins `smallest GGUF is 13 GB` for `LFM2.5-24B-A2B` while the live build
says `9 GB`. Four earlier runs (`44206920194`, `44195647662`, `44176093280`, `44142734842`)
failed the same way. `registry-liveness` is green across the same window, but no durable rule
makes a landing verify either battery, so a red live battery on main is currently noise nobody
owns — exactly the failure mode issue #2900 was filed for.

## What Changes

1. **Re-pin the derived trend data.** Run the fixed render order (`sync-registry` →
   `sync-quant-catalog` → `render-trend-list-matrix` → `render-engine-skill-gap` →
   `skills-validate` → checks → unit) so `tests/fixtures/trend-list-matrix.json` and
   `tests/fixtures/hub-snapshot.json` match the CURRENT trending and the four red metal/16
   cells agree with the live numbers.
2. **ADDED requirement — Post-merge live verification duty.** Every landing onto main ends by
   reading the newest main runs of `registry-liveness.yml` and `ci-hf-live.yml`; both must be
   green. A `ci-hf-live` red whose diff is fixture-vs-live drift opens a trend-refresh issue;
   re-running it away is forbidden.
3. **ADDED requirement — replayable check target.** `make post-merge-live-check`
   (`scripts/post_merge_live_check.py`) prints one verdict line per battery (newest main run id,
   event, conclusion) plus the `check-trend-list-matrix` fingerprint read, exits non-zero on any
   red battery or fingerprint mismatch, and is unit-tested with the API read seam faked and the
   comparison logic real.

Out of scope (filed as #2901, linked both ways): the between-renders staleness alarm — detecting
fixture drift the day it happens instead of five red runs later.

4. **The new trending carries four unskilled engines.** `basalt`, `edge0`, `qwen-warp` and
   `smolmaxxing` arrive with the re-pin; the lane files their tracking issues
   (`make -s spawn-engine-skill-issues` → #2902–#2905) and records dated decisions in
   `data/unsupported-engines.json` in the same batch, re-rendering `engine-skill-gap` to 0
   unresolved.
5. **A data-dependent test guard made data-independent.** The re-pin made the store's global
   order coincide with the 8 GB tier ranking, breaking `test_card_gate_measured_vram`'s
   store-order inequality; the guard becomes reversal invariance (a reversed store must give the
   same card list), which tests the code rather than today's data.
