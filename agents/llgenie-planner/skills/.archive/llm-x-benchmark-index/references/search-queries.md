# Per-backend lightbrd.com search queries (verified Sep 28 2026)

Run one group per backend over a **last-30-day** window; within a group rank by
**interactions (likes/loves + comments) first, then t/s**. Capture the engine
and the specific model each post tested. All queries were verified live on the
lightbrd mirror (rendering fetch required — see SKILL.md Cloudflare pitfall).

## Backend A — NVIDIA / CUDA (8-48 GB scope)

- `rtx 3090 tokens per second qwen`
- `rtx 5090 32gb tokens per second`
- `rtx 4090 tokens per second llm`
- `rtx 3090 vs 5090 27b tokens`
- `freetoken gpu llm tokens per second`
- `bonsai 2 ternary 27b tokens`
- `qwen3.8-27b dflash speculative tokens`
- `"tokens per second" llm rtx`
- `open weight llm benchmark gpu`

High-signal engines/models these surface: DFlash2 (z-lab/dflash) speculative
decode on vLLM/SGLang; llama.cpp + MTP; Strata (125B MoE on 12-24 GB); Muse
Glimmer 30B (Meta, DFlash on RTX 5090); Bonsai 2 27B ternary across 8-48 GB.

## Backend B — Apple / Metal

- `mlx apple silicon tokens per second model`
- `mac m4 mlx local llm tokens per second`
- `mlxfast bonsai tokens per second`
- `tensorfold dflash mlx qwen tokens per second`
- `mac m series local llm tokens per second`

High-signal: MLX + TensorFold (ashhart/TensorFold); MLX-fast Bonsai 2
(Layr-Labs/mlxfast-bonsai2-27b-engine, ~237 tok/s on 16 GB Mac); DFlash-mlx.

## Backend C — CPU (sparse on X)

- `llm tokens per second no gpu cpu`
- `llama.cpp cpu only tokens per second`

Keep this table thin by nature; most CPU signal comes via offload-capable
engines (FreeToken, llama.cpp cpu) surfaced by the CUDA/engine queries.
