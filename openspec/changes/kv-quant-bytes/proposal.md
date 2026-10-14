# KV cache sizing: every documented type, no silent fp16

## Why

`kv_bytes_per_token()` — the helper every context/KV budget in `scripts/llama_serve.py`
reads — had exactly two outcomes: fp16, or `f16_bytes / 4` for `q4_0`/`q4_1`/`q5_0`/`q5_1`.
Everything else fell through to `return f16_bytes`, so an **8-bit** cache (`q8_0`, and the
`int8`/`k8v4` types `skills/engines/strata/SKILL.md` documents as `--kv q4_0|int8|k8v4`) was
billed at the **fp16** size — a **2x overestimate**, in the direction that halves the context
a card can actually serve.

Measured on the reporting host (RTX 4090 Laptop, 16 GB VRAM, 62 GiB RAM, Qwen3.8-Flash-Next
125B `qwen4exp`, 48 layers, `n_head_kv=2`, key=value=256, `ctx_train=262144`):

| KV type | computed before | reality |
|---|---|---|
| `int8` / `q8_0` @ 262,144 | 6.00 GiB (fp16 branch) | **3.0 GiB** computed, **3.6 GB** as Strata reports it |

Two further defects fall out of the same line: the type was a bare module constant
(`KV_QUANT`), and each helper that needed it read the constant itself, so the arithmetic that
sized the context and the `-ctk`/`-ctv` flags the launch emitted could drift apart with
nothing to catch it.

## What changes

- **A table, not a fallback.** `KV_BYTES_PER_ELEMENT` sizes every type llama.cpp and the
  skills accept: `f16`/`fp16`/`bf16` = 2, `q8_0`/`int8` = 1, `k8v4` = 0.75, `q5_0`/`q5_1` =
  0.6875, `q4_0`/`q4_1`/`iq4_nl` = 0.5. `kv_bytes_per_element()` raises a `ValueError` naming
  the known types for anything else — **never** a silent fp16 assumption.
- **One resolution, one answer.** `kv_quant_for(meta, ctx, card_bytes)` resolves the cache type
  for this card and this context; `build_command` passes that value to the offload decision,
  emits it as `-ctk`/`-ctv`, and the plan a user (or `--dry`) reads prints the same value with
  the cache size it implies. The helper and the launch cannot disagree.
- **Policy unchanged.** `KV_QUANT` (`q4_0`) remains what llgenie serves — 42 launch cases pin
  that value — so this is a correctness change, not a behaviour change. A
  `prefer_larger=True` hook derives the largest type that still fits the same budget
  (fp16 → 8-bit → floor); it is what #245 (derive every serving parameter from the hardware)
  will switch on, and it is covered by tests so the two cannot drift.
- **Makefile wiring**: `tests/test_kv_quant_bytes.py` is added to the `test-unit` recipes, and
  the wiring guard (`make check-wiring`) must stay green.

## Scope

- Not covered: the *policy* of preferring a larger cache on capable cards (#245), the Strata
  launch passing any of these parameters at all (#245), and `k8v4`'s exact packing overhead
  (0.75 bytes/element is the nominal K8/V4 split).
- No engine image, params file, or registry data changes.
