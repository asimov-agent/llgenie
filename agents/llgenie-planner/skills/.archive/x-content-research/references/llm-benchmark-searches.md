# LLM benchmark searches on lightbrd (per-backend)

Verified query library (Sep 2026), refined by live probing for **maximum
matches per backend**. Run one group per backend over a rolling 30-day window.
Rank by **interactions (likes/loves + comments) first, then t/s**; capture the
specific model + engine each post tested. Four groups: NVIDIA/CUDA, Metal/MLX,
CPU, and a General cross-backend t/s-trend group.

## A — NVIDIA / CUDA (8–48 GB scope)
- `rtx tokens per second llm` (broad — highest match count)
- `rtx 3090 tokens per second qwen` (spec-decode)
- `rtx 5090 32gb tokens per second`
- `rtx 4090 tokens per second llm`
- `rtx 3090 vs 5090 27b tokens` (cross-card)
- `freetoken gpu llm tokens per second` (big MoE on small GPU)
- `bonsai 2 ternary 27b tokens` (low-end ternary model)
- `qwen3.8-27b dflash speculative tokens`
- `open weight llm benchmark gpu`

## B — Apple / Metal
- `mlx tokens per second` (broad — highest match count)
- `mlx apple silicon tokens per second model`
- `mac m4 mlx local llm tokens per second`
- `mlxfast bonsai tokens per second`
- `tensorfold dflash mlx qwen tokens per second`

## C — CPU (sparse on X)
- `llm tokens per second no gpu cpu`
- `llama.cpp cpu only tokens per second`
- `local llm tokens per second gpu` (catches CPU-offload engines)

## General — cross-backend t/s trend
- `"tokens per second" llm`
- `tokens per second benchmark llm`
- `local llm tokens per second gpu`
- `open weight llm benchmark gpu`

## Notes
- **Engine names are not query terms.** `freeToken engine moE small gpu`
  returns nothing; query model + hardware qualifier instead.
- **CPU signal** mostly comes from offload engines (FreeToken, llama.cpp CPU)
  found under CUDA/engine queries; keep the CPU table thin, never fabricated.
- **Verify HF links** before publishing: marketing names differ from repo IDs
  (e.g. Bonsai 2 → `prism-ml/Ternary-Bonsai-2-27B-gguf`).
- **Every entry carries its links — model HF link AND engine repo link.** A
  trending list is only useful if each row is clickable: the model links to its
  Hugging Face page, and each engine measurement links to the engine's repo
  (or the specific model/draft repo that produced the figure, e.g. a DFlash2
  draft under z-lab). No bare engine or model names without a link. Verify the
  obscure engine repos by `web_search` rather than guessing (e.g. TensorFold →
  `ashhart/TensorFold`, DFlash2 → `z-lab/dflash`).
- **Label workload-specific peaks** (e.g. DFlash2 context-lookup) as mode, not
  typical chat speed.
- **Parse t/s ranges with `re.findall` + max, not `re.search`.** A value like
  `"35.5-43.7"` or `"67-71"` — `re.search` returns the FIRST number (35.5, 67),
  not the peak. When sorting a table by highest t/s, extract all numbers and
  take the max, or the sort is wrong.
- **Sort by the extracted t/s field, never by regex-scanning the whole row.**
  Scanning a rendered row for numbers picks up the year (2026) and date digits
  as the "max", silently breaking the sort. Compute the peak from the structured
  t/s field, then sort on that.
