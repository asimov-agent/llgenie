# Tasks

- [x] 1. Write the proposal + spec for the KV cache sizing change (issue #247).
- [x] 2. Add `KV_BYTES_PER_ELEMENT` (f16/fp16/bf16 = 2; q8_0/int8 = 1; k8v4 = 0.75;
      q5_0/q5_1 = 0.6875; q4_0/q4_1/iq4_nl = 0.5) and keep `KV_QUANT` as the documented floor.
- [x] 3. Add `kv_bytes_per_element()`: an explicit size per type, a loud `ValueError`
      naming the known types for anything else — never a silent fp16 fallback.
- [x] 4. Rewrite `kv_bytes_per_token()` on the table (`per_element * layers * n_kv * (k+v)`),
      so 8-bit is exactly half of fp16 and `k8v4` is 0.375 of it.
- [x] 5. Add `kv_quant_for(meta, ctx, card_bytes)` and `serve_plan(meta, card_bytes)`:
      one resolution for the cache type and the context (the budget is sized at the floor,
      the type is derived for that same context).
- [x] 6. Thread that value through `tuned_context()`, `gpu_offload_layers()` and
      `build_command()`; emit `-ctk`/`-ctv` from it, and print it (type + GiB) in the serve
      plan, which `--dry` shows before it returns.
- [x] 7. Add `prefer_larger` as the explicit policy hook (fp16 → 8-bit → floor), defaulting
      off so the 42 existing launch cases keep the q4_0 they pin.
- [x] 8. Add `tests/test_kv_quant_bytes.py`: the skill-parsed type table, the ratio checks,
      the loud failure, the derivation, the launch/helper agreement, and the reported model
      at 262,144 (≈3 GiB, not 6).
- [x] 9. Wire the new test file into the `test-unit` recipes.
- [x] 10. Verify: `make lint`, the new file plus `tests/test_llama_ai.py` (269 passed),
      `make check-wiring`, `make check-engine-skill-gap`, and `make openspec-validate
      NAME=kv-quant-bytes` all green before the PR is opened.
- [x] 12. Add the explicit override (`LLGENIE_KV_QUANT`): a validated type name, or `auto`
      for the largest that fits — resolved in one place (`resolve_kv_quant`) and used by the
      budget, the offload decision, the flags and the plan. Unset keeps the floor.
- [x] 13. Document the knob in the README (`## Environment variables`), with its values, the
      default and the loud-failure behaviour.
- [x] 14. Pin the knob in `tests/test_kv_quant_bytes.py` (default, named, auto, unknown, and
      that it reaches `-ngl`), so the served type can differ from the module constant safely.
- [x] 11. Commit as one atomic change, push the branch, open the PR against
      `asimov-agent/llgenie` linking issue #247, and stop there for review (never merge).
