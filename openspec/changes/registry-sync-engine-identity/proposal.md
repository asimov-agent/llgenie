# Proposal: registry-sync-engine-identity

Issue: #223

## Why

`registry-sync` failed its own `test-unit` gate on the 2026-10-13 registry
(run 38422539548, `2 failed, 4220 passed`). Both failures were the same defect:
`tests/test_strata_download.py` addressed an engine by its **position** in the
offer row, but the engine order is vendored upstream data and legitimately
changes between syncs.

Upstream added a TensorFold measurement on a **DGX Spark** (an NVIDIA/CUDA box),
which `measurement_backend` classifies as CUDA. `rank_engines` sorts same-backend
engines by measured t/s, so for `qwen3.8-flash-next-125b` on a CUDA host
TensorFold (67 t/s) now sorts above llama.cpp (33.7 t/s):
`strata, tensorfold, llama.cpp, mlx`. The old tests assumed
`engines[1] == llama.cpp` and engine choice `"2" == llama.cpp`.

The sync PR was skipped, so `main` keeps the October-12 registry and llgenie's
trend data ages. Any future upstream t/s change that reorders engines blocks the
sync the same way.

## What Changes

- `test_offer_gives_strata_its_own_plan_and_llama_cpp_its_own` selects `strata`
  and `llama.cpp` by **id** (`by_id`), not `engines[0]`/`engines[1]`. The
  assertions are unchanged (Strata's own plan path, llama.cpp's Unsloth repo).
- `test_interactive_pick_llama_cpp_for_the_same_model_gets_its_own_files` derives
  llama.cpp's 1-based position from the same `offer()` it drives the PTY with
  (`_engine_no()`), instead of a hardcoded `"2"`.

Test-only: no product code, no data change.

- `AGENTS.md` gains a durable rule — **"Tests address engines by id, never by
  index"** — so this class cannot recur: the engine order is vendored upstream
  data, and any future test that pins a named engine to a fixed index (or a
  literal interactive choice) is called out as a defect.
- `AGENTS.md` gains a second durable rule — **"Out-of-scope work is a SEPARATE,
  linked issue — never prose"**: every issue/PR closes its scope with a `Not
  covered` section and files each deferred item as its own linked issue. This
  change exercises it: the ranking rule deferred here is filed as #225.

## Out of scope

The engine-ranking policy itself (whether an engine measured on a beefier CUDA
box should outrank llama.cpp on a small card). That is upstream data + the
defined `rank_engines` rule; this change only stops the tests from pinning the
order it produces.

## Impact

`tests/test_strata_download.py`, `AGENTS.md`.

Both tests pass on the old registry (llama.cpp = engine `2`) and the new one
(llama.cpp = engine `3`), so the change is registry-agnostic.
