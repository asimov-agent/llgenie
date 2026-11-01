# engine(arch): ternary/prism routing (#1092) — change record

## What changed

A model whose own record states ternary packings is served **only** by the
`llama.cpp-prism` fork, on every arch — the picker no longer offers it plain
`llama.cpp`, whose PQ2_0/PTQ1_0 tensor types (GGML_TYPE 142/143) it reads as
invalid.

- `scripts/model_engine_pick.py`
  - new `is_ternary(model)`: the Ternary signal comes from the SYNCED store — the
    model's own `type` ("LLM (ternary)"), a `ternary` field, a "PrismML Ternary"
    `full_name`, or a `prism-ml/Ternary-*` Hub repo — never from the file extension.
  - `rank_engines.add()` gates non-prism engines out for a ternary model. Before,
    a CPU host picked the plain-`llama.cpp` phone run (@ 6.0, measured CPU = rank 0)
    over the prism fork's CUDA figure (@ 128, cross-backend = rank 3), offering a
    pair that cannot load the file. Prism has cpu/vulkan/metal variants, so every
    host still gets a runnable cell.
- `tests/fixtures/trend-list-matrix.json` regenerated **hermetically** against the
  committed `tests/fixtures/hub-snapshot.json` — the ONLY deltas are ternary-model
  rows (all Bonsai → `llama.cpp (PrismML fork)`; `Bonsai 2 4B` has 0 plain-`llama.cpp`
  rows across all 81 cases), zero non-ternary drift. `hub-snapshot.json` untouched.
- `tests/test_trend_pick.py` new `test_ternary_model_routes_only_to_the_prism_fork`.
- `tests/test_trend_list_matrix.py` — deleted the #1073 canary +
  #1099 "golden not regenerated" guard, exactly as their own docstrings direct once
  the routing lands and the golden is regenerated for real.

## Why hermetic regen

`make render-trend-list-matrix` records the LIVE Hub and rewrites both the fixture
and `hub-snapshot.json`; running it would fold live-data drift into the fixture on
top of this PR's behavioral change. Replaying the committed snapshot keeps the diff
limited to the fix and leaves the verification gate (`make check-trend-list-matrix`)
hermetic and green in the same repo state.

## Verification

- `make check-trend-list-matrix` → OK (81 cases, recorded snapshot), exit 0.
- hermetic unit: test_trend_pick + test_trend_list_matrix = 61 passed (incl. the new
  ternary test); test_model_engine_pick 13 passed; test_engine_capabilities +
  test_engine_image_matrix 29 passed; `is_ternary` matches the store's signals on all
  112 models with zero mismatches.
- (live `make test-install-trend` needs a real `make install` + GGUF download + Hub
  route and is not a hermetic CI gate; its model-list-ordering diff on this host is a
  live-fit artifact, unrelated to engine routing.)

## Out of scope

- `measurement_backend`'s CPU-default fix is already on main (#1099) — not re-done.
- Re-enabling the disabled `registry-sync` / `registry-sync-review` pipelines is
  owner/repo-admin only (thread notes), so the trending-store sync itself cannot be
  re-run by this lane; this PR fixes the code that consumes the synced data.
