# quant-catalog refresh against live HF (#1712)

`ci-hf-live`'s `Live check-quant-catalog` gate (the main-only real-Hub comparison) redded because the
committed `data/trending-quant-catalog.json` pointed at artifacts `unsloth/Qwen3.8-Flash-Next-GGUF`
removed — the resolve links answered 404/410. It is a live-network, never-a-PR-check gate, so a red
flags either upstream HF catalog drift or a transient live-call failure; this was drift, persistent
across three consecutive main tips.

## The refresh

`make sync-quant-catalog` regenerates `data/trending-quant-catalog.json` plus the two test fixtures
(`tests/fixtures/quant-catalog-hub-snapshot.json`, `tests/fixtures/trending-quant-catalog.json`) from
the real registry + live Hub. The read-only generator lists quant plans and resolves links — it never
downloads a model. The dead `UD-*.gguf` links for `qwen3.8-flash-next-125b` / `-4090-hybrid` (llama.cpp,
vLLM, SGLang) were replaced by the live artifacts the repo now serves (UD-Q2_0, UD-IQ2_XS, the
4-split UD-Q3_K_XL, and so on).

## Prove-the-guard

On the **stale** table, `make check-quant-catalog LIVE=1` reds, naming the 404/410 links. On the
**regenerated** tree the same command passes (`table == generator`). The refresh is deterministic:
re-running the sync reproduces the committed table, and the recorded-snapshot hermetic gate
(`check-quant-catalog` without LIVE) is green after it. Drift, not flake: the same dead links failed
across main tips `90bab322`, `d104a156`, `1fc00f30`. Implements #1712.
