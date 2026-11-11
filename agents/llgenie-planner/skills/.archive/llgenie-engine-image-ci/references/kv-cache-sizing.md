# KV cache sizing for llgenie model analysis

## The arithmetic

KV cache bytes per token (for the layers that actually grow with context):

```
fp16: 2 bytes/element
8-bit (int8 / q8_0 / k8v4): 1 byte/element  = fp16 / 2
q4_0 / q4_1 / q5_*: 0.5 byte/element       = fp16 / 4

per_token = 2.0 * layers * n_head_kv * (key_len + val_len)   # fp16
```

`layers` is the count that grows with context — for a hybrid/strata model use
`full_attention_interval` (KV grows on ~1/N of layers), not `n_layer`.

## The pitfall: a silent default branch bills unknown quants as fp16

`kv_bytes_per_token(meta, quant)` in `scripts/llama_serve.py` has one explicit
branch (`q4_0`/`q5_*` → ÷4) and otherwise `return f16_bytes`. So `int8`,
`k8v4`, `q8_0` — exactly the KV types the Strata skill documents
(`--kv q4_0|int8|k8v4`) — are billed as fp16, a **2× overestimate** for 8-bit.
On a 16 GiB card that is the difference between "262,144 does not fit"
(6.00 GiB computed) and "262,144 fits next to the compute buffers"
(3.00 GiB real).

Generalizable rule: when a helper has a silent fall-through default for an
unhandled enum value, verify it handles EVERY value the surrounding docs/skills
name, and make the fallback loud (or an explicitly documented conservative
default) rather than silently the largest/smallest option. A new KV type added
elsewhere is then mis-billed with no test failure.

## Reading the model's real numbers

- The model's own ceiling is in the GGUF: `ctx_train` (context_length),
  `n_layer` (block_count), `n_head_kv` (head_count_kv), `key_length`/
  `value_length`, `full_attention_interval`. llgenie's `read_model_meta_fast`
  already reads these — so the window is known at launch and simply may not be
  consumed by the launch path.
- Use `read_model_meta_fast` (header-only, struct-based) over `GGUFReader`:
  the pinned `gguf` package's tensor builder raises `ValueError: np.uint32(N)
  is not a valid GGMLQuantizationType` on newer ggml types.
- Run the extraction in the test image with the model dir mounted `:ro`
  (`-v /models:/models:ro`) — the host python lacks `gguf`/`numpy`.

## Why a big window on a small card needs streaming

Weights (e.g. 70.6 GiB across 2 shards) vs a 15.99 GiB card ⇒ weights cannot be
resident ⇒ experts and KV must stream. At 262,144 the KV is 3.00 GiB (int8) or
1.50 GiB (q4_0) but 6.00 GiB at fp16 — of a card that must also hold the compute
buffer. So the KV *type* decides whether the full window coexists with fast
compute; `--kv-streaming on` stops VRAM capping the window, and
`--vram-reserve-mib` protects the compute buffer. This is the case Strata exists
to serve, and the one a launch that derives nothing computes worst.
