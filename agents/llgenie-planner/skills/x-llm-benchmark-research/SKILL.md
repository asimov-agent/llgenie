---
name: x-llm-benchmark-research
description: "Use when gathering open-weight LLM data from X posts."
version: 1.0.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [x, twitter, llm, benchmark, research, lightbrd, open-weights]
---

# X LLM Benchmark Research

Gather open-weight LLM benchmark and popularity data from X posts and compile it into a structured tracking README (e.g. a `trending-local-llms` repo).

## When to use

- Building/updating a list of open-weight LLMs people actually run and like.
- Collecting measured t/s, VRAM, and inference-engine data per model.
- Ranking models by X engagement (likes/views/downloads), not benchmark scores.

## Critical: how to reach X content

**Firecrawl (web_extract) does NOT support x.com** — it returns `Website Not Supported`. Do not waste calls on it.

**Use the lightbrd.com mirror** (a working X frontend) via `web_extract`:

```
https://lightbrd.com/search?f=tweets&q=QUERY
```

- URL-encode the query. `f=tweets` filters to posts.
- lightbrd returns real X posts with author, timestamp, text, and engagement (likes/views).
- Nitter instances (nitter.net, xcancel.com, nitter.poast.org, nitter.privacydev.net) are mostly DOWN or blocked — don't rely on them.
- lightbrd results are truncated; the full text is saved to a cache file (footer gives the path) — read it with `read_file` if you need the omitted middle.

## Workflow

1. **Search lightbrd** for the models/backends you care about. Good query patterns:
   - `"tokens per second" local llm`
   - `open weight llm benchmark gpu`
   - `qwen3.8-27b local speed tokens`
   - `gemma 4 12b tokens per second`
   - `mlx apple silicon tokens per second benchmark`
   - `48GB 64GB 96GB VRAM llm benchmark`
   - `128GB 256GB unified memory llm benchmark`
   - `llama 4 open weights release`, `deepseek open weights local`, `glm kimi nemotron open weight local`
2. **Extract per model**: full name, params, license, HF link, VRAM/RAM, measured t/s + the hardware it was measured on, and the inference engine.
3. **Rank by engagement** — use view counts, like counts, HF download counts, and repeated mentions from the posts. This is directional, not a precise like-count.
4. **Verify HF links** with `web_search` (e.g. `Qwen3-235B-A22B huggingface`). Model IDs often differ from the marketing name (e.g. Qwen3.8-Max → `Qwen/Qwen3.8-2.4T-A95B`, Mach-1 → `SyzygyResearch/Mach-1-Additive-35B`).

## README structure (what the user wants)

- **Ranked by X love** (engagement), not benchmarks — a "Most loved" table with: rank, model, full name, HF link, why people love it, **CUDA t/s**, **Metal t/s**, VRAM, engine.
- **GPU type first**: CUDA (NVIDIA), then CPU, then Metal (Apple Silicon).
- **VRAM tiers** within each: 6/8/12/16/24/32/48/64/96/128/256/384/512/576 GB (CUDA), 48/64/96/128/256/512 (Metal), by RAM (CPU).
- **Same column pattern per tier**: Model | Params | License | HF | VRAM | t/s | Engine.
- **Sort by highest t/s** within each tier.
- **One specific engine per model** (llama.cpp, Ollama, vLLM, MLX, TensorFold, FreeToken, etc.) — not a list.
- Include a **speed-evolution** section (same model, faster engines over months) and an **engine guide**.

## Pitfalls

- **Never fabricate an engine from the model name — and do not expect the prompt to
  stop it.** When a post names no engine, the engine must NOT be invented out of the
  model/vendor/quant tokens (`Nvidia/Qwen3.8-Flash-Next-FP4-Local` is a MODEL, `NVFP4`
  a QUANT — neither is an engine). Tell the agent that, in ONE shared rule expanded
  into every leg, and name the forbidden tokens explicitly. But **a prompt is
  necessary and not sufficient**: an engine rule that spelled out the exact forbidden
  token still saw a leg write `engine: "FP4-Local"` for that post on the next refresh.
  So the refusal must be MECHANICAL where the value becomes data — at ingest, dropping
  that measurement and logging the model, the engine and the source post (a t/s with no
  engine named by the post is not a valid entry).
- **A refusal heuristic must key on a PROVABLE shape, and be proved against the whole
  suite.** An engine name never contains a quantization token (`FP4`, `NVFP4`, `Q8_0`,
  `AWQ`, `GPTQ`, `GGUF`, `EXL2`), so that alone proves fabrication. "The engine name is
  a substring of the model name" is NOT proof — real engines legitimately appear in
  model names (`WebLLM` inside `Llama-3.1-8B (WebLLM)`, `MLX` heading
  `mlx-community/…`), and a substring rule drops a legitimate measurement. Keep a
  genuinely unknown engine PASSING so validation keeps failing loudly for a human;
  run the full suite (not just your fixture) after adding any data-shape guard.
- **A validation failure that recurs across consecutive refresh PRs (same field,
  same kind of wrong value) is a defect in the search prompt, the contract, or the
  ingest code — fix it THERE with a test, not by letting fix-bot patch every PR.**
  The recurring failure is the signal that the gatherer is producing the bad value;
  a per-PR repair re-derives the class fix by hand each time and never stops the
  next PR from failing the same way.
- **When a prompt rule must be byte-identical across the search legs, define it
  ONCE and expand it into every leg — never keep N inline copies.** Four
  byte-identical copies of an engine rule drift silently: one leg gets edited, the
  others keep the old wording, and a guard that reads the shared definition stops
  matching. Follow the repo's own convention (a `DIM_ASK`/`ENGINE_ASK` constant
  expanded by every leg).
- **Label data honestly**: community-reported on X is directional, not lab-grade. Mark estimates as `(est)`. Don't present vendor claims as independent benchmarks.
- **Don't scrape/replicate one person's curation** as your own. Compile from broad public X signal and attribute each model to its actual creator. If the user wants a specific profile's picks, have them paste the model names.
- **Don't mention the user's hardware** in the README unless asked — keep it generic.
- **VRAM figures are estimates** from quant sizes unless a post gives a measured number (e.g. Qwen3.8-27B has a precise VRAM-sizing formula).
- **High-VRAM tiers (48 GB+)** lean on a few detailed X writeups — fewer measured numbers there.
- **HF links for huge models** (Qwen3-235B, MiniMax, GLM-5.2, Kimi, DeepSeek-V4-Flash, Qwen3.8-Max, Mach-1) are often filled from naming convention — verify before relying on them.

## Engines to know

- **Ollama** — easiest, CUDA/CPU/Metal.
- **llama.cpp** — max control, custom quants (Bonsai 2, Mirai 2.4-bit).
- **FreeToken** (UC Berkeley) — 2-4x faster than Ollama, runs big MoE on small GPUs.
- **vLLM / SGLang** — production serving, big MoE.
- **MLX** — fastest on Apple Silicon.
- **TensorFold** — speculative decoding on Mac, 3-6x on memory-bound Macs.
- **TensorRT-LLM** — max NVIDIA perf.
- **LiteRT** — Google's local runtime (Gemma 4 + Antigravity).
