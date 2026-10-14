# 2026-10-14 — KV cache sizing: every documented type, no silent fp16 (issue #247)

## The defect

`scripts/llama_serve.py::kv_bytes_per_token()` had two outcomes, not eleven:

```python
f16_bytes = 2.0 * layers * n_kv * (key_len + val_len)
if quant in ("q4_0", "q4_1", "q5_0", "q5_1"):
    return f16_bytes / 4.0
return f16_bytes          # <- 8-bit billed as fp16
```

So `q8_0`, and the `int8` / `k8v4` types `skills/engines/strata/SKILL.md` documents
(`--kv q4_0|int8|k8v4`), were billed at the **fp16** size — 2x too much. A wrong KV bill
shrinks the context a card is allowed to serve, which is the same user-visible symptom as the
Strata launch gap (#245), one layer down.

## Measured (reporting host)

RTX 4090 Laptop, **16376 MiB** VRAM, **62 GiB** RAM, Qwen3.8-Flash-Next 125B (`qwen4exp`,
48 layers, `n_head_kv=2`, key=value=256, `full_attention_interval=4`, `ctx_train=262144`,
70.63 GiB of shards). Read with the repo's own `read_model_meta_fast` + the fixed helper:

| | before | after |
|---|---|---|
| `int8`/`q8_0` @ 262,144 | 6.00 GiB (fp16 branch) | **3.00 GiB** |
| `int8` @ 65,536 | 1.50 GiB | **0.75 GiB** |
| `k8v4` @ 262,144 | 6.00 GiB | **2.25 GiB** |
| `q4_0` @ 262,144 | 1.50 GiB | 1.50 GiB (unchanged) |

The engine's own report agrees with the new arithmetic, not the old: Strata logged
`KV streaming needs ~3.6 GB` of RAM for the 262,144-token 8-bit cache (engine overhead on top
of 3.00 GiB), and 0.9 GB for the 65,536-token one — exactly 4x for 4x the context.

## The change

- `KV_BYTES_PER_ELEMENT` — a table: `f16`/`fp16`/`bf16` = 2, `q8_0`/`int8` = 1, `k8v4` = 0.75,
  `q5_0`/`q5_1` = 0.6875, `q4_0`/`q4_1`/`iq4_nl` = 0.5.
- `kv_bytes_per_element(quant)` — explicit size, `ValueError` (naming the known types) for
  anything else. No silent fp16, ever.
- `kv_quant_for(meta, ctx, card_bytes)` + `serve_plan(meta, card_bytes)` — one resolution of
  the cache type for this card and context; `build_command` feeds it to the offload decision,
  emits it as `-ctk`/`-ctv`, and the plan line (visible in `--dry`) prints the type and its
  GiB for the context. The helper and the launch cannot disagree.
- `prefer_larger=True` — the explicit policy hook for a larger cache (fp16 → 8-bit → floor,
  never one that does not fit). **Off by default**: `KV_QUANT` (`q4_0`) is still what llgenie
  serves, because 42 existing launch cases pin that value. Switching the policy on is #245's
  decision (derive every serving parameter from the hardware), and the hook is tested so the
  two cannot drift.

## Serving more, on purpose

The default stays the floor, but the *served* type is no longer the module constant:
`LLGENIE_KV_QUANT` takes a validated type name (`int8`, `k8v4`, `f16`, ...) or `auto` for the
largest type that still fits this card and context, resolved once in `resolve_kv_quant()` and
used by the budget, the offload decision, the flags and the plan. So a host that can afford a
bigger cache can ask for it today — `LLGENIE_KV_QUANT=auto llgenie` — while everyone else keeps
the q4_0 cache they had.

## Tests

`tests/test_kv_quant_bytes.py` (wired into `make test-unit`): the type list is *parsed from
`skills/engines/*/SKILL.md`* (the strata skill yields `q4_0`, `int8`, `k8v4`) and every type
found must be sized, so a new documented type fails loudly instead of falling through; the
ratio checks (8-bit = fp16/2, `k8v4` = 0.375, `q4_0` = 1/4); seven unknown-type cases; the
derivation across card sizes; the launch/helper agreement; and the reported model at 262,144
(≈3 GiB, and exactly half of its own fp16 figure).

## Boundary

- The default *policy* does not change (that is #245), and no engine image, params file or
  registry data is touched.
- `k8v4`'s 0.75 bytes/element is the nominal K8/V4 split; the engine's own packing overhead is
  not modelled (the same caveat the q4_0 figure always had).
