# Trending Local LLMs

A living, detailed list of **open-weight** LLMs that actually make a difference for local deployment. Every figure is **community-reported on X** (real benchmark posts, not vendor claims), with the hardware and engine it was measured on. This README is **automatically regenerated** from `data/models.json` — see [AGENTS.md](AGENTS.md) and `skills/gather-data.md`.

**How the ranking works.** Models are grouped 🔥 **trending** (seen in the last 7 days) → 🕑 **recent** (last 30 days) → 💤 **stale** (older, kept with their last measurement date). Within a group they rank by **Trend = buzz + speed**:
- **buzz** — for every distinct X post in the last 7 days: 1 + 0.5×log2(1 + likes + 2×comments + 3×reshares) + 0.25×log10(1 + views). Every post counts, so a model many people are posting about beats one post with a few interactions; engagement adds on top with diminishing returns.
- **speed** — log2(1 + t/s ÷ 10) for the model's fastest measurement on consumer hardware (GPUs up to 48 GB, Apple Silicon, CPU; datacenter parts never count), only while it is trending: 10 t/s → +1, 70 → +3, 150 → +4.

Ties go to more posts, then the highest t/s. t/s is always shown **per engine**, with the hardware and quant it was measured on.

> Last generated: 2026-10-05 23:49 UTC. Source: lightbrd.com mirror (X posts).

---

## ❤️ Most loved open-weight models on X (ranked by trend: 7-day buzz + speed)

Best measured t/s per backend; the full list of measurements is in the backend tables below.

| Model | Status | Trend | CUDA t/s (best) | Metal t/s (best) | CPU t/s (best) | ROCm t/s (best) | VRAM | Why people love it |
|---|---|---|---|---|---|---|---|---|
| [**Qwen3.8-Flash-Next 125B**](https://huggingface.co/Qwen/Qwen3.8-Flash-Next)<br><sub>Qwen3.8-Flash-Next-125B · 125B (MoE) · Apache 2.0</sub> | 🔥 trending<br><sub>last seen 2026-10-05</sub> | **41.9**<br><sub>buzz 38.2 · 8 posts · speed +3.7 (124 t/s, RTX 4090 24GB)</sub> | **124** t/s<br>[Strata](https://github.com/Niko1221/Strata) · RTX 4090 24GB · IQ2_XS, 128GB RAM<br><sub>+2 more</sub> | **92** t/s<br>[TensorFold](https://github.com/ashhart/TensorFold) · Apple Silicon · MLX 4-bit | — | **60** t/s<br>[Strata](https://github.com/Niko1221/Strata) · RX 7900 XTX 24GB · ROCm<br><sub>+4 more</sub> | 12GB | Qwen3.8-Flash-Next-125B — see source posts. |
| [**Qwen3.8-27B**](https://huggingface.co/Qwen/Qwen3.8-27B)<br><sub>Qwen3.8-27B-Instruct · 27B · Apache 2.0</sub> | 🔥 trending<br><sub>last seen 2026-10-04</sub> | **22.3**<br><sub>buzz 18 · 6 posts · speed +4.3 (189 t/s, M5 Max (Apple Silicon))</sub> | **133** t/s<br>[DFlash2](https://github.com/z-lab/dflash) · RTX 3090 24GB · DFlash2 speculative decode + lookup-augmented drafting, optimized vLLM, prefix caching, quantized KV cache; ~133 t/s real chat, ~138 t/s DFlash2+lookup, up to 381 t/s longer-verification + context lookup<br><sub>+4 more</sub> | **189** t/s<br>[TensorFold](https://github.com/ashhart/TensorFold) · M5 Max (Apple Silicon) · MLX 4-bit, DFlash2 drafter<br><sub>+5 more</sub> | — | **65** t/s<br>[llama.cpp (LaurentZuijdwijk fork)](https://github.com/LaurentZuijdwijk/llama.cpp) · Strix Halo (AMD Ryzen AI Max APU) · adaptive speculation (llama.cpp fork), decode t/s; 440 t/s prefill; up from 44 t/s on mainline<br><sub>+4 more</sub> | 16GB | Flagship local model. 384K views on release. 262K ctx (1M via YaRN). |
| [**Bonsai 2 27B**](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf)<br><sub>Ternary-Bonsai-2-27B · 27B · Apache 2.0</sub> | 🔥 trending<br><sub>last seen 2026-10-05</sub> | **17**<br><sub>buzz 12.4 · 5 posts · speed +4.6 (237 t/s, Apple Silicon 16GB Mac)</sub> | **146** t/s<br>[llama.cpp (PrismML fork)](https://github.com/PrismML-Eng/llama.cpp) · RTX 5090 · PTQ1_0 ternary (5.95 GB weights), thinking mode<br><sub>+5 more</sub> | **237** t/s<br>[MLX-fast (Bonsai 2)](https://github.com/Layr-Labs/mlxfast-bonsai2-27b-engine) · Apple Silicon 16GB Mac · mlx.fast 4-bit | — | — | 12GB | PrismML 1.75-bit ternary compression of Qwen3.8-27B; ~98.2% capability in 5.9 GB. 11,792 downloads in 5 days. Runs big-VRAM-quality (262K ctx, MTP, vision on 16 GB) on old low-end cards. |
| [**RavenX-Conjecture-Qwen3-8B-MLX**](https://huggingface.co/deadbydawn101/RavenX-Conjecture-Qwen3-8B-MLX)<br><sub>RavenX-Conjecture-Qwen3-8B-MLX · 8B · Apache 2.0</sub> | 🔥 trending<br><sub>last seen 2026-09-29</sub> | **6.1**<br><sub>buzz 3.7 · 1 post · speed +2.4 (42 t/s, M3 (Apple Silicon))</sub> | — | **42** t/s<br>[MLX](https://github.com/ml-explore/mlx) · M3 (Apple Silicon) · MLX | — | — | 8GB | RavenX-Conjecture-Qwen3-8B-MLX — see source posts. |
| [**Qwen3.6-35B-A3B**](https://huggingface.co/Qwen/Qwen3.6-35B-A3B)<br><sub>Qwen3.6-35B-A3B · 35B (MoE, 3B active) · Apache 2.0</sub> | 🔥 trending<br><sub>last seen 2026-09-29</sub> | **5**<br><sub>buzz 2.7 · 1 post · speed +2.3 (39.3 t/s, 8GB GPU (est, vendor-claimed MoE weight offload))</sub> | **39.3** t/s<br>[FreeToken](https://github.com/FlashML-org/FreeToken) · 8GB GPU (est, vendor-claimed MoE weight offload) · MoE, experts across VRAM/RAM | — | — | — | 8GB | Qwen3.6-35B-A3B — see source posts. |
| [**Ornith 1.5**](https://huggingface.co/ornith-ai/Ornith-1.5-9B)<br><sub>Ornith 1.5 · 9B · Apache 2.0</sub> | 🔥 trending<br><sub>last seen 2026-09-29</sub> | **4.8**<br><sub>buzz 2.2 · 1 post · speed +2.6 (50 t/s, MacBook Pro M5 48GB)</sub> | — | **50** t/s<br>[MLX](https://github.com/ml-explore/mlx) · MacBook Pro M5 48GB · MLX 4-bit | — | — | 48GB | Ornith 1.5 — see source posts. |
| [**Qwen3 8B**](https://huggingface.co/Qwen/Qwen3-8B)<br><sub>Qwen3-8B · 8B · Apache 2.0</sub> | 🕑 recent<br><sub>last seen 2026-09-12</sub> | **0**<br><sub>no posts in 7 days</sub> | **100** t/s<br>[Ollama](https://github.com/ollama/ollama) · RTX 4060 · Q4_K_M | — | — | — | 8GB | The default 8 GB pick. Fast, Apache 2.0. |
| [**Gemma 4 12B**](https://huggingface.co/google/gemma-4-12B-it)<br><sub>gemma-4-12B-it · 12B · Gemma</sub> | 🕑 recent<br><sub>last seen 2026-09-19</sub> | **0**<br><sub>no posts in 7 days</sub> | **99.7** t/s<br>[llama.cpp](https://github.com/ggml-org/llama.cpp) · RTX 4090 Laptop · Q4 | **49.67** t/s<br>[llama.cpp](https://github.com/ggml-org/llama.cpp) · Apple Silicon · Q4 | — | — | 9GB | Best overall personal-agent model. Multimodal + audio, 256K ctx. |
| [**Qwen3 14B**](https://huggingface.co/Qwen/Qwen3-14B)<br><sub>Qwen3-14B · 14B · Apache 2.0</sub> | 🕑 recent<br><sub>last seen 2026-09-15</sub> | **0**<br><sub>no posts in 7 days</sub> | **65** t/s<br>[Ollama](https://github.com/ollama/ollama) · RTX 3090 · Q4_K_M | — | — | — | 9GB | 2M HF downloads. The community mid-size favorite. |
| [**Qwen 3.6 27B**](https://huggingface.co/Qwen/Qwen3.6-27B)<br><sub>Qwen3.6-27B · 27B · Apache 2.0</sub> | 🕑 recent<br><sub>last seen 2026-09-10</sub> | **0**<br><sub>no posts in 7 days</sub> | **37** t/s<br>[llama.cpp](https://github.com/ggml-org/llama.cpp) · RTX 3090 · Q4_K_M | — | — | — | 18GB | Strongest local coding model (SWE-bench 77.2%). |
| [**Gemma 4 E2B**](https://huggingface.co/google/gemma-4-E2B)<br><sub>gemma-4-E2B · 2B · Gemma</sub> | 🕑 recent<br><sub>last seen 2026-09-05</sub> | **0**<br><sub>no posts in 7 days</sub> | — | — | **9** t/s<br>[LiteRT](https://github.com/google-ai-edge/LiteRT) · Raspberry Pi 5 (CPU) · 1432 MB peak RAM | — | 2GB | Google's compact Gemma 4 edge model runs on-device via LiteRT on a Raspberry Pi 5: 99 tok/s prefill and 9 tok/s decode at 1432 MB peak RAM, fully offline. |
| [**Muse Glimmer 30B**](https://huggingface.co/meta-models/Muse-Glimmer-30B)<br><sub>Muse-Glimmer-30B · 30B · Apache 2.0</sub> | 💤 stale<br><sub>last seen 2026-08-10</sub> | **0**<br><sub>no posts in 7 days</sub> | **233** t/s<br>[llama.cpp](https://github.com/ggml-org/llama.cpp) · RTX 5090 · 4-bit | **50** t/s<br>[llama.cpp](https://github.com/ggml-org/llama.cpp) · M5 Max (Apple Silicon) · 4-bit | — | — | 24GB | Meta Superintelligence 30B agentic model, Apache 2.0. Fits 24/32 GB at 4-bit (<20GB weights + KV + vision + spec draft). DFlash drafter gives 3.1x decode on RTX 5090. |
| [**Llama 3.1 8B**](https://huggingface.co/meta-llama/Llama-3.1-8B)<br><sub>Llama-3.1-8B · 8B · Llama 3.1 Community License</sub> | 💤 stale<br><sub>last seen 2026-07-06</sub> | **0**<br><sub>no posts in 7 days</sub> | — | — | — | **96** t/s<br>[vLLM](https://github.com/vllm-project/vllm) · RX 7900 XTX · ROCm 7.2, continuous batching + PagedAttention; generation t/s on IDLE distributed network | 8GB | Llama-3.1-8B — see source posts. |
| [**DeepSeek R1 1.5B**](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B)<br><sub>DeepSeek-R1-Distill-Qwen-1.5B · 1.5B · MIT</sub> | 💤 stale<br><sub>last seen 2026-06-25</sub> | **0**<br><sub>no posts in 7 days</sub> | — | — | **4** t/s<br>[Ollama](https://github.com/ollama/ollama) · Raspberry Pi 4B 2GB (CPU) · quantized | — | 2GB | DeepSeek R1 1.5B served fully offline by Ollama on a 7-year-old Raspberry Pi 4B at 4 tok/s under 5 W, no network or API needed. |

---

## 🧭 Which inference engine runs what

Best measured t/s per model on each engine (🟦 CUDA · 🟩 Metal · 🟨 CPU · 🟪 ROCm). Only engines with at least one measurement are shown.

| Model | [llama.cpp](https://github.com/ggml-org/llama.cpp) | [MLX](https://github.com/ml-explore/mlx) | [Ollama](https://github.com/ollama/ollama) | [TensorFold](https://github.com/ashhart/TensorFold) | [DFlash2](https://github.com/z-lab/dflash) | [ExLlamaV3 (ROCm fork)](https://github.com/CarouselAether/rocm_exl3) | [FreeToken](https://github.com/FlashML-org/FreeToken) | [LiteRT](https://github.com/google-ai-edge/LiteRT) | [llama.cpp (LaurentZuijdwijk fork)](https://github.com/LaurentZuijdwijk/llama.cpp) | [llama.cpp (PrismML fork)](https://github.com/PrismML-Eng/llama.cpp) | [MLX-fast (Bonsai 2)](https://github.com/Layr-Labs/mlxfast-bonsai2-27b-engine) | [SGLang](https://github.com/sgl-project/sglang) | [Strata](https://github.com/Niko1221/Strata) | [vLLM](https://github.com/vllm-project/vllm) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Qwen3.8-Flash-Next 125B** | 🟦 21 | — | — | 🟩 92 | — | 🟪 34.7 | — | — | — | — | — | — | 🟦 124<br>🟪 60 | — |
| **Qwen3.8-27B** | 🟦 43.7<br>🟪 51.8 | 🟩 80 | — | 🟩 189 | 🟦 133 | — | — | — | 🟪 65 | — | — | 🟦 44 | — | — |
| **Bonsai 2 27B** | — | — | — | — | — | — | — | — | — | 🟦 146 | 🟩 237 | — | — | — |
| **RavenX-Conjecture-Qwen3-8B-MLX** | — | 🟩 42 | — | — | — | — | — | — | — | — | — | — | — | — |
| **Qwen3.6-35B-A3B** | — | — | — | — | — | — | 🟦 39.3 | — | — | — | — | — | — | — |
| **Ornith 1.5** | — | 🟩 50 | — | — | — | — | — | — | — | — | — | — | — | — |
| **Qwen3 8B** | — | — | 🟦 100 | — | — | — | — | — | — | — | — | — | — | — |
| **Gemma 4 12B** | 🟦 99.7<br>🟩 49.67 | — | — | — | — | — | — | — | — | — | — | — | — | — |
| **Qwen3 14B** | — | — | 🟦 65 | — | — | — | — | — | — | — | — | — | — | — |
| **Qwen 3.6 27B** | 🟦 37 | — | — | — | — | — | — | — | — | — | — | — | — | — |
| **Gemma 4 E2B** | — | — | — | — | — | — | — | 🟨 9 | — | — | — | — | — | — |
| **Muse Glimmer 30B** | 🟦 233<br>🟩 50 | — | — | — | — | — | — | — | — | — | — | — | — | — |
| **Llama 3.1 8B** | — | — | — | — | — | — | — | — | — | — | — | — | — | 🟪 96 |
| **DeepSeek R1 1.5B** | — | — | 🟨 4 | — | — | — | — | — | — | — | — | — | — | — |

---

# 🟦 CUDA — NVIDIA GPUs (8–48 GB)

| Model | Params | License | VRAM | Peak t/s | Measurements (engine · t/s · hardware · quant · date) |
|---|---|---|---|---|---|
| [**Muse Glimmer 30B**](https://huggingface.co/meta-models/Muse-Glimmer-30B) | 30B | Apache 2.0 | 24GB | 233 | [llama.cpp](https://github.com/ggml-org/llama.cpp) **233** · RTX 5090 · 4-bit · 2026-08-10 |
| [**Bonsai 2 27B**](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf) | 27B | Apache 2.0 | 12GB | 146 | [llama.cpp (PrismML fork)](https://github.com/PrismML-Eng/llama.cpp) **146** · RTX 5090 · PTQ1_0 ternary (5.95 GB weights), thinking mode · 2026-10-05<br>[llama.cpp (PrismML fork)](https://github.com/PrismML-Eng/llama.cpp) **91** · RTX 4070 12GB · PTQ1_0-mtp-lean (6.3 GB) · 2026-09-26<br>[llama.cpp (PrismML fork)](https://github.com/PrismML-Eng/llama.cpp) **75** · RTX 5080 16GB · ternary · 2026-10-02<br>[llama.cpp (PrismML fork)](https://github.com/PrismML-Eng/llama.cpp) **71** · RTX 5060 Ti 16GB · ternary, author conditions · 2026-10-01<br>[llama.cpp (PrismML fork)](https://github.com/PrismML-Eng/llama.cpp) **54.1** · RTX 5060 Ti 16GB · ternary, Japanese text · 2026-10-01<br>[llama.cpp (PrismML fork)](https://github.com/PrismML-Eng/llama.cpp) **50** · RTX 3060 12GB · PTQ1_0 ternary MTP (5.95 GB weights), 125K ctx; ~50 t/s fresh, ~22 t/s avg agentic coding · 2026-10-02 |
| [**Qwen3.8-27B**](https://huggingface.co/Qwen/Qwen3.8-27B) | 27B | Apache 2.0 | 16GB | 133 | [DFlash2](https://github.com/z-lab/dflash) **133** · RTX 3090 24GB · DFlash2 speculative decode + lookup-augmented drafting, optimized vLLM, prefix caching, quantized KV cache; ~133 t/s real chat, ~138 t/s DFlash2+lookup, up to 381 t/s longer-verification + context lookup · 2026-10-02<br>[DFlash2](https://github.com/z-lab/dflash) **90** · RTX 4090 24GB · Q4_K_M + Unsloth UD-Q4_K_XL, Z-Lab DFlash2 drafter, patched llama.cpp, parallel block diffusion drafting; ~87 t/s @ 30K ctx to ~83 t/s @ 110K ctx, 24GB VRAM · 2026-10-02<br>[SGLang](https://github.com/sgl-project/sglang) **44** · DGX Spark · DFlash2 spec-decode draft head · 2026-09-29<br>[llama.cpp](https://github.com/ggml-org/llama.cpp) **43.7** · RTX 5090 Laptop · Q4_K_M · 2026-09-18<br>[SGLang](https://github.com/sgl-project/sglang) **12** · DGX Spark · no spec-decode · 2026-09-29 |
| [**Qwen3.8-Flash-Next 125B**](https://huggingface.co/Qwen/Qwen3.8-Flash-Next) | 125B (MoE) | Apache 2.0 | 12GB | 124 | [Strata](https://github.com/Niko1221/Strata) **124** · RTX 4090 24GB · IQ2_XS, 128GB RAM · 2026-10-05<br>[Strata](https://github.com/Niko1221/Strata) **94** · RTX 5070 12GB · Q20 (2-bit-class), MoE experts across GPU/RAM/SSD, 64GB RAM · 2026-10-05<br>[llama.cpp](https://github.com/ggml-org/llama.cpp) **21** · RTX 4090 24GB · UD-Q4_K_XL (111 GB across 4 GGUF shards), MoE experts offloaded to 110 GB DDR4 system RAM, 250K ctx, no MTP/DFlash, -b 4096 -ub 4096; ~20.97 t/s decode @ 250K, ~364 t/s prefill · 2026-10-03 |
| [**Qwen3 8B**](https://huggingface.co/Qwen/Qwen3-8B) | 8B | Apache 2.0 | 8GB | 100 | [Ollama](https://github.com/ollama/ollama) **100** · RTX 4060 · Q4_K_M · 2026-09-12 |
| [**Gemma 4 12B**](https://huggingface.co/google/gemma-4-12B-it) | 12B | Gemma | 9GB | 99.7 | [llama.cpp](https://github.com/ggml-org/llama.cpp) **99.7** · RTX 4090 Laptop · Q4 · 2026-09-19 |
| [**Qwen3 14B**](https://huggingface.co/Qwen/Qwen3-14B) | 14B | Apache 2.0 | 9GB | 65 | [Ollama](https://github.com/ollama/ollama) **65** · RTX 3090 · Q4_K_M · 2026-09-15 |
| [**Qwen3.6-35B-A3B**](https://huggingface.co/Qwen/Qwen3.6-35B-A3B) | 35B (MoE, 3B active) | Apache 2.0 | 8GB | 39.3 | [FreeToken](https://github.com/FlashML-org/FreeToken) **39.3** · 8GB GPU (est, vendor-claimed MoE weight offload) · MoE, experts across VRAM/RAM · 2026-09-29 |
| [**Qwen 3.6 27B**](https://huggingface.co/Qwen/Qwen3.6-27B) | 27B | Apache 2.0 | 18GB | 37 | [llama.cpp](https://github.com/ggml-org/llama.cpp) **37** · RTX 3090 · Q4_K_M · 2026-09-10 |

---

# 🟪 ROCm — AMD GPUs (8–48 GB)

| Model | Params | License | VRAM | Peak t/s | Measurements (engine · t/s · hardware · quant · date) |
|---|---|---|---|---|---|
| [**Llama 3.1 8B**](https://huggingface.co/meta-llama/Llama-3.1-8B) | 8B | Llama 3.1 Community License | 8GB | 96 | [vLLM](https://github.com/vllm-project/vllm) **96** · RX 7900 XTX · ROCm 7.2, continuous batching + PagedAttention; generation t/s on IDLE distributed network · 2026-07-06 |
| [**Qwen3.8-27B**](https://huggingface.co/Qwen/Qwen3.8-27B) | 27B | Apache 2.0 | 16GB | 65 | [llama.cpp (LaurentZuijdwijk fork)](https://github.com/LaurentZuijdwijk/llama.cpp) **65** · Strix Halo (AMD Ryzen AI Max APU) · adaptive speculation (llama.cpp fork), decode t/s; 440 t/s prefill; up from 44 t/s on mainline · 2026-08-25<br>[llama.cpp](https://github.com/ggml-org/llama.cpp) **51.8** · Radeon AI PRO R9700 32GB · llama.cpp (Vulkan), MTP=2; AMD day-0 pre-verification generation speed · 2026-09-06<br>[llama.cpp](https://github.com/ggml-org/llama.cpp) **50** · AMD AI Pro R9700 · llama.cpp (Vulkan), 256k tokens, 8-bit/16-bit KV; decodes close to 50 t/s short and long generation · 2026-08-17<br>[llama.cpp](https://github.com/ggml-org/llama.cpp) **33** · Strix Halo 128GB (GMKtec Evo-X2) · Q3_K_XL, 64K ctx, vision; ~33 tok/s total across four concurrent lanes; portable 'Vulcan' fork by Nathanw1014 · 2026-09-15<br>[llama.cpp](https://github.com/ggml-org/llama.cpp) **26.39** · Radeon 8060S / Strix Halo (Ryzen AI Max+ 395) · llama.cpp (Vulkan), Qwen3.8-27B UD-Q4_K_XL + DFlash2 drafter Q8_0 (n=4), spec-decode; ~2x vs 10.54 t/s stock decode at 32K · 2026-08-20 |
| [**Qwen3.8-Flash-Next 125B**](https://huggingface.co/Qwen/Qwen3.8-Flash-Next) | 125B (MoE) | Apache 2.0 | 12GB | 60 | [Strata](https://github.com/Niko1221/Strata) **60** · RX 7900 XTX 24GB · ROCm · 2026-10-05<br>[Strata](https://github.com/Niko1221/Strata) **60** · RX 9070 XT 16GB · ROCm · 2026-10-05<br>[Strata](https://github.com/Niko1221/Strata) **40** · Strix Halo (Ryzen AI Max APU) · ROCm · 2026-10-04<br>[Strata](https://github.com/Niko1221/Strata) **40** · RX 7900 XT 20GB + 80GB DDR4 (WSL2) · ROCm, MoE experts across GPU/RAM; ~30-40 t/s · 2026-09-29<br>[ExLlamaV3 (ROCm fork)](https://github.com/CarouselAether/rocm_exl3) **34.7** · 32GB Radeon · EXL3 5.05 bpw, Q8 KV, ROCm · 2026-10-04 |

> AMD figures land here by **hardware** (Radeon / RX / Strix Halo / ROCm), whichever API ran them: ROCm/HIP (vLLM, SGLang, Ollama, llama.cpp `GGML_HIP`) or Vulkan (llama.cpp `GGML_VULKAN`, often the faster llama.cpp path on consumer Radeon). Vulkan on an NVIDIA card stays in the CUDA table.

---

# 🟨 CPU — no GPU

| Model | Params | License | VRAM | Peak t/s | Measurements (engine · t/s · hardware · quant · date) |
|---|---|---|---|---|---|
| [**Gemma 4 E2B**](https://huggingface.co/google/gemma-4-E2B) | 2B | Gemma | 2GB | 9 | [LiteRT](https://github.com/google-ai-edge/LiteRT) **9** · Raspberry Pi 5 (CPU) · 1432 MB peak RAM · 2026-09-05 |
| [**DeepSeek R1 1.5B**](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B) | 1.5B | MIT | 2GB | 4 | [Ollama](https://github.com/ollama/ollama) **4** · Raspberry Pi 4B 2GB (CPU) · quantized · 2026-06-25 |

> CPU inference is **memory-bandwidth bound**. Use Q4 quant + a fast CPU build (AVX-512/AMX).

---

# 🟩 Metal — Apple Silicon (unified memory)

| Model | Params | License | VRAM | Peak t/s | Measurements (engine · t/s · hardware · quant · date) |
|---|---|---|---|---|---|
| [**Bonsai 2 27B**](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf) | 27B | Apache 2.0 | 12GB | 237 | [MLX-fast (Bonsai 2)](https://github.com/Layr-Labs/mlxfast-bonsai2-27b-engine) **237** · Apple Silicon 16GB Mac · mlx.fast 4-bit · 2026-09-26 |
| [**Qwen3.8-27B**](https://huggingface.co/Qwen/Qwen3.8-27B) | 27B | Apache 2.0 | 16GB | 189 | [TensorFold](https://github.com/ashhart/TensorFold) **189** · M5 Max (Apple Silicon) · MLX 4-bit, DFlash2 drafter · 2026-09-30<br>[TensorFold](https://github.com/ashhart/TensorFold) **154** · M4 Max (Apple Silicon) · MLX 4-bit, DFlash drafter · 2026-10-01<br>[TensorFold](https://github.com/ashhart/TensorFold) **124** · Apple Silicon · MLX 4-bit · 2026-09-27<br>[MLX](https://github.com/ml-explore/mlx) **80** · M3 Ultra · MLX high-quant · 2026-10-04<br>[MLX](https://github.com/ml-explore/mlx) **44.6** · M3 Max 96GB (Apple Silicon) · MLX 4-bit, z-lab DFlash2 8-bit drafter · 2026-09-27<br>[TensorFold](https://github.com/ashhart/TensorFold) **41.5** · M3 Max 96GB (Apple Silicon) · MLX 4-bit, z-lab DFlash2 8-bit drafter · 2026-09-27 |
| [**Qwen3.8-Flash-Next 125B**](https://huggingface.co/Qwen/Qwen3.8-Flash-Next) | 125B (MoE) | Apache 2.0 | 12GB | 92 | [TensorFold](https://github.com/ashhart/TensorFold) **92** · Apple Silicon · MLX 4-bit · 2026-09-27 |
| [**Ornith 1.5**](https://huggingface.co/ornith-ai/Ornith-1.5-9B) | 9B | Apache 2.0 | 48GB | 50 | [MLX](https://github.com/ml-explore/mlx) **50** · MacBook Pro M5 48GB · MLX 4-bit · 2026-09-29 |
| [**Muse Glimmer 30B**](https://huggingface.co/meta-models/Muse-Glimmer-30B) | 30B | Apache 2.0 | 24GB | 50 | [llama.cpp](https://github.com/ggml-org/llama.cpp) **50** · M5 Max (Apple Silicon) · 4-bit · 2026-08-10 |
| [**Gemma 4 12B**](https://huggingface.co/google/gemma-4-12B-it) | 12B | Gemma | 9GB | 49.67 | [llama.cpp](https://github.com/ggml-org/llama.cpp) **49.67** · Apple Silicon · Q4 · 2026-09-19 |
| [**RavenX-Conjecture-Qwen3-8B-MLX**](https://huggingface.co/deadbydawn101/RavenX-Conjecture-Qwen3-8B-MLX) | 8B | Apache 2.0 | 8GB | 42 | [MLX](https://github.com/ml-explore/mlx) **42** · M3 (Apple Silicon) · MLX · 2026-09-29 |

> On Apple Silicon, **MLX** is the fastest engine; **TensorFold** adds speculative decoding (3–6x on memory-bound Macs); **MLX-fast Bonsai 2** (Layr-Labs/mlxfast-bonsai2-27b-engine) pushes Ternary Bonsai 2 27B to ~237 tok/s on a 16 GB Mac.

---

## ⚙️ Inference engine / server guide

| Engine | Backend | Models measured | Best for |
|---|---|---|---|
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | CUDA / ROCm / CPU / Metal | 5 | Max control, custom quants; AMD via ROCm/HIP or Vulkan |
| [llama.cpp (PrismML fork)](https://github.com/PrismML-Eng/llama.cpp) | CUDA / CPU / Metal | 1 | PrismML's llama.cpp fork (prism branch) — required for Ternary Bonsai 2 PTQ1_0/PQ2_0 (stock llama.cpp rejects them) |
| [Ollama](https://github.com/ollama/ollama) | CUDA / ROCm / CPU / Metal | 3 | Easiest start |
| [FreeToken](https://github.com/FlashML-org/FreeToken) | CUDA | 1 | Big MoE on small GPUs |
| [vLLM](https://github.com/vllm-project/vllm) | CUDA / ROCm | 1 | Production serving, high throughput |
| [SGLang](https://github.com/sgl-project/sglang) | CUDA / ROCm | 1 | High-throughput serving |
| [MLX](https://github.com/ml-explore/mlx) | Metal | 3 | Fastest on Apple Silicon |
| [TensorFold](https://github.com/ashhart/TensorFold) | Metal | 2 | Speculative decoding on Mac, 3-6x |
| [TensorRT-LLM](https://github.com/NVIDIA/TensorRT-LLM) | CUDA | 0 | Max NVIDIA perf |
| [LiteRT](https://github.com/google-ai-edge/LiteRT) | CUDA / Metal | 1 | Google local runtime |
| [Strata](https://github.com/Niko1221/Strata) | CUDA / ROCm | 1 | Runs big MoE (Qwen3.8-Flash-Next 125B) on 8-48 GB GPUs; experts across GPU/RAM/SSD, speculative decoding ~1.6-1.8x; AMD RX 7900 XT/XTX, 9070 (XT), R9700 on Linux via --backend hip (ROCm, experimental) |
| [MLX-fast (Bonsai 2)](https://github.com/Layr-Labs/mlxfast-bonsai2-27b-engine) | Metal | 1 | Speedup benchmark engine for Ternary Bonsai 2 27B on Apple Silicon; ~237 tok/s decode on 16 GB Mac (mlx.fast, Yukon/Layr-Labs) |
| [DFlash2](https://github.com/z-lab/dflash) | CUDA | 1 | Speculative decoding + context-lookup (Inco AI / syv-ai); Qwen3.8-27B ~118-133 tok/s chat, up to ~381 tok/s context-lookup on 24 GB RTX 3090 |
| [WebLLM](https://github.com/mlc-ai/web-llm) | CUDA / Metal | 0 | In-browser LLM inference accelerated with WebGPU (MLC-LLM). |
| [ExLlamaV3 (ROCm fork)](https://github.com/CarouselAether/rocm_exl3) | ROCm | 1 | Auto-registered from https://lightbrd.com/Oluwaphilemon1/status/2106576426883227694 — A fork of exllamav3 for ROCm. |
| [llama.cpp (LaurentZuijdwijk fork)](https://github.com/LaurentZuijdwijk/llama.cpp) | ROCm | 1 | Auto-registered from https://lightbrd.com/laurent_zw/status/2092215141144162519 — llama.cpp with adaptive speculative decoding (--spec-draft-adaptive) and a Vulkan backend tuned for AMD Strix Halo. 4.7x |

**Quick picks:** Ollama (just works) · llama.cpp (gaming laptop, max speed) · FreeToken (big MoE on small GPU) · MLX + TensorFold + MLX-fast (Mac) · Strata (125B MoE on 12–24 GB) · vLLM + DFlash2 (spec decode) · llama.cpp Vulkan / ROCm (AMD Radeon) · llama.cpp CPU (tiny/edge).

---

## How to contribute

- Update `data/models.json` (add/refresh a model row with real X-sourced engagement and per-engine t/s), then run `python3 scripts/update_trending.py` to regenerate the README.
- Include: full model name, HF link, license, params, type, VRAM tier, a **measured** t/s + **engine + hardware + quant**, and the source X post (a `…/status/<id>` URL, so engagement is counted once per post).
- Prefer numbers from real X benchmark posts over vendor claims. Data is **community-reported on X** — directional, not lab-grade; mark projections `(est)`.
- All changes go through a **feature branch + PR**; automation never pushes to/merges `master` directly.

## License

Apache License 2.0. See [LICENSE](LICENSE).
