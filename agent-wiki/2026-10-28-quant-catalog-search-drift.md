# quant-catalog-search-drift — 2026-10-28

## What changed

- `scripts/gen_trending_quant_catalog.py`
  - `compare()` takes a `probe` (default `_probe_status`) and no longer fails on a mere absence: a
    committed plan the generation dropped is probed on its own link. `ok`/`gated` → **NOTE** ("still
    reachable (…), kept, not a failure"); `dead` → **FAILURE** naming the URL and `404/410`.
  - `_classify_missing_plan()` — the one place a dropped plan's absence is classified (a plan with no
    URL reads `dead`, so an unverifiable plan is never silently blessed).
  - `carry_over()` (sync only) re-inserts a still-reachable committed plan into the fresh table and
    returns `(payload, kept, dropped)`; `main()` prints `[sync] kept …` / `[sync] dropped …` and
    re-renders the JSON **after** the merge, so the file it writes is the file the gate then passes.
- `tests/test_quant_catalog_compare.py` (new) — the rule through the real `compare()`/`carry_over()`
  and the **unpatched** `_probe_status()` against a real loopback `http.server` answering 200 / 401 /
  404. No mocks: real sockets, real status classification, production classifier. Hermetic because it
  never touches the Hub.
- Three existing tests encoded the old verdict and are **updated, not duplicated**:
  `test_quant_generator_edges.py::test_check_fails_when_a_committed_plan_is_lost` → the dead-link
  case (plus a new sibling asserting the reachable case is green), and
  `test_trending_quant_catalog.py`'s lost-plan/changed-plan pair → the split rule (a reachable loss
  is a note on both sides, a dead one still fails).

## Why

Measured on `main` `ea80ab4`: `make check-quant-catalog` red with 7 failures for a reason no PR
caused — six `SolsticeAI/Nanbeige4.3-33B-mlx-*` plans (HTTP 401, gated) and
`ToPo-ToPo/Ornith-1.5-35B-A3B-mlx-4bit` (HTTP 200, still public) dropped by the live search. The
table is read from a SEARCH (`sort=downloads`), so page churn is normal; the gate treated it as a
broken catalog, and the forced sync then deleted a downloadable plan from the picker.

## Decisions

- **The committed catalog is the artifact under test; the live search is an input, not an oracle.**
  The one question a plan's absence raises is "does anything still serve this download?", and the
  plan's own URL answers it. A search result is not evidence a download died.
- **Dead stays dead.** 404/410 still fails the shared gate, and a transport error reads `dead` on
  purpose: blessing an unverifiable link would be exactly the weakening the issue forbids.
- **The sync is additive in both directions now.** Dropping a plan is a deletion of product surface
  (the picker stops offering it), so it needs a probe's verdict and a printed reason, not merely a
  page that stopped listing it.
- **Probe cost is bounded by the diff.** Only plans a generation dropped are probed, so the gate is
  free on a clean catalog and costs a handful of ranged GETs on a drifted one.
- **No new network in the unit suite.** The rule is proven on loopback, so it stays in the hermetic
  gate instead of joining `test-hub-live`'s exclusions — while `make check-quant-catalog` itself
  exercises the live Hub, where the real evidence lives.

## Gates

- `make check-quant-catalog` — green on the drifted store (the 7 plans report as notes).
- `make test-unit` (new files + the 3 updated tests), `make lint`, `make check-wiring`,
  `make check-docs`, `make openspec-validate NAME=quant-catalog-search-drift` — green.

## Related

Issue [#769](https://github.com/asimov-agent/llgenie/issues/769) · #418 (a gated link is not a dead
one — the vocabulary this reuses) · #736 (the drift gate) · #737 (the plan order still follows the
live ranking, out of scope) · #760 (the PR whose CI this blocked).
