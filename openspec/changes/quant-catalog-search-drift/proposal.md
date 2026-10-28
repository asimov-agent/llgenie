# quant-catalog-search-drift — proposal

Issue: [#769](https://github.com/asimov-agent/llgenie/issues/769)

## Why

`make check-quant-catalog` is the one gate every PR runs, and it went red on `main` `ea80ab4` for a
reason no PR caused: 7 of the committed catalog's plans stopped being generated — the six
`SolsticeAI/Nanbeige4.3-33B-mlx-*` plans (their repo now answers HTTP 401, gated) and
`ToPo-ToPo/Ornith-1.5-35B-A3B-mlx-4bit` (HTTP 200, still public, dropped by the live search).

The table is regenerated from a SEARCH (`huggingface.co` `sort=downloads`), so the same set of plans
comes back in a different order, a page moves, or a repo becomes gated — and `compare()` called every
one of those a FAILURE. The only way out was a data commit on a feature branch, and the sync that
produced it DROPPED the still-downloadable `ToPo-ToPo/Ornith-1.5-35B-A3B-mlx-4bit` plan from the
picker's table until a later page happened to return it.

Two different events were collapsed into one verdict: a repo that became gated/deleted (correct to
drop) and a repo that fell off a search result page (not correct to drop).

## What Changes

- `compare()` probes the link of a committed plan the generation dropped, and splits the verdict:
  `ok`/`gated` → a **NOTE** (kept, the gate stays green); `dead` (404/410) → a **FAILURE**, because
  nothing serves that download any more.
- `carry_over()` (sync only) re-inserts a still-reachable committed plan into the fresh table and
  prints why it was kept; a dead one is dropped with its reason. `compare()` then agrees with the
  table the sync wrote.
- The probe is injected (`probe=`), defaulting to the production `_probe_status`, so a clean catalog
  costs zero requests and a test can drive the real classifier.

## Out of scope

- The catalog's dependence on the live download ranking — #737, filed separately.
- Per-class CI stage selection — #824.
