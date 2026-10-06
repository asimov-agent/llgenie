---
name: engine-dflash2
description: "Use when a model's best t/s is from DFlash2: it is a block-diffusion drafter, not a server; serve the target via sglang (DFLASH) with the matching drafter checkpoint."
engine: "DFlash2"
id: dflash2
repo: https://github.com/z-lab/dflash
ref: v0.1.0
ref_kind: tag
pinned: 07ebd93db9f472af339b644bb70221ad8428328a
verified: "2026-10-05"
license: MIT
servable: via
via: [sglang, vllm]
backends: [cuda]
os: [linux]
formats: [safetensors]
drafters:
  "Qwen/Qwen3.8-27B": z-lab/Qwen3.8-27B-DFlash2
  "meta-models/Muse-Glimmer-30B": z-lab/Muse-Glimmer-30B-DFlash2
via_launch:
  sglang: "--speculative-algorithm DFLASH --speculative-draft-model-path {drafter} --speculative-num-draft-tokens 8"
upstream_watch: [README.md, pyproject.toml]
---

# DFlash2 — drafter, served via a host engine

`z-lab/dflash` is a client plus a collection of **block-diffusion draft models** for
speculative decoding. It has no OpenAI server of its own. The index's DFlash2 t/s
numbers (e.g. Qwen3.8-27B at about 133 t/s on an RTX 3090) come from a host engine running
a DFlash2 drafter.

## How llgenie serves it

1. Install the host engine skill: `sglang` (DFLASH is in the 0.5.x release).
2. Launch the target with the drafter tied to it (`drafters:` above):
   `sglang serve --model-path Qwen/Qwen3.8-27B ... --speculative-algorithm DFLASH
   --speculative-draft-model-path z-lab/Qwen3.8-27B-DFlash2 --speculative-num-draft-tokens 8`.
3. vLLM support is still an open PR (#52816), so it is **not** used until it is
   released. llama.cpp support is PR #27342, and the Prism fork has `--spec-type draft-dflash`.

## Hardware parameters

These are the host engine's (sglang: CUDA 13, sm75+). Note that DFlash2 rejects a
**quantized target LM head** (SGLang refuses it), so the target must keep a
bf16/fp16 head. Each drafter is tied to one target model family.
