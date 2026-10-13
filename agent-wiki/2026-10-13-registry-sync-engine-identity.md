# 2026-10-13 registry-sync engine identity (issue #223, merged PR #224)

`registry-sync` failed its own `test-unit` gate on the 2026-10-13 registry
(run 38422539548, `2 failed, 4220 passed`) and skipped opening the sync PR.

## Root cause

Two tests in `tests/test_strata_download.py` addressed an engine by its
**position** in the offer row. The engine order is vendored upstream data:
`rank_engines` sorts same-backend engines by measured t/s, so a new upstream
measurement on CUDA-class hardware reorders a model's engines with no llgenie
code change. Upstream added a TensorFold measurement on a **DGX Spark**
(NVIDIA/CUDA, 67 t/s) that sorted above llama.cpp (33.7 t/s) for
`qwen3.8-flash-next-125b` (`strata, tensorfold, llama.cpp, mlx`), so the
hardcoded `engines[1]` / interactive choice `"2"` silently became TensorFold.

## Fix (merged as `fa438fc`, PR #224)

- `test_offer_gives_strata_its_own_plan_and_llama_cpp_its_own` selects
  `strata` / `llama.cpp` by id (`by_id`); assertions unchanged.
- `test_interactive_pick_llama_cpp_for_the_same_model_gets_its_own_files`
  derives llama.cpp's 1-based position from the same `offer()` the PTY drives
  (`_engine_no`), instead of a hardcoded `"2"`.
- `AGENTS.md` gained two durable rules:
  - "Tests address engines by id, never by index" (the engine order is vendored
    upstream data).
  - "Out-of-scope work is a SEPARATE, linked issue — never prose" (every
    issue/PR closes its scope with a `Not covered` section and files each
    deferred item as its own linked issue, both ways).

Verified in `llgenie/test:latest`: the unfixed tests fail on the 2026-10-13
registry exactly as CI did; the fixed tests pass on both the old and new
registry (llama.cpp = engine 2 vs 3).

## Re-run after the merge

`registry-sync` run 38474370820 on `main` succeeded: the gate reported
`4222 passed, 3 deselected`, `check-registry` OK
(`generated_utc=2026-10-13T14:31:40Z`, 23 models), and it opened PR #226
(`chore/registry-sync`, `75f103c`).

PR #226 validated: branch re-checked locally (`check-registry`,
`check-quant-catalog`, `check-trend-list-matrix` all OK; the two
previously-failing tests pass), and its pipeline (run 38476028181) is green.

## Follow-ups filed (out of scope here)

- #225 — the ranking rule itself: `rank_engines` ranks by raw t/s within a
  backend class; a DGX Spark measurement outranks a small consumer card's own
  engine. `_CUDA_HW` includes `dgx`/`gb10`.
- #227 — the 8–48 GB consumer scope is prose, not a checked invariant (the
  registry carries a `128GB` tier entry, `cyber-frost-3.8-mlx`).
- #228 — the `(arch, ram, vram) → best model + best engine` mock grid coverage,
  and whether a per-engine `make`-generated list is wanted.
- #229 — 7 registry engines have no llgenie skill/params/image
  (`mlx-serve`, `oMLX`, `ExLlamaV3`, `MegaCapybara`, `omlx-exl3`,
  `llama.cpp (LlamAmpere fork)`, `glm-flash-lite`), carried by
  `ALLOW_UNSKILLED=1`, never servable.

## Status

Fix merged and validated; the weekly sync loop works again. The four
follow-ups above are open and are the remaining work on the trend/engine pick.
