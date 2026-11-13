# data/models.json — Model Contract

`data/models.json` is the **single source of truth** for the trending-local-llms
index. The README is generated from it. Every model is one object in the
`models` array. **No duplicate models** (by `id` or `name`) are allowed — the
validator enforces this.

> **Machine-checkable schema:** the exact contract is defined in
> `data/model_contract.json` (JSON Schema 2020-12). `scripts/validate.py`
> (check_schema) validates `models.json` against it on every run. The prose
> below summarises it; the schema is authoritative.

## Top-level shape

```json
{
  "generated_utc": "2026-09-28T12:00:00Z",
  "note": "...",
  "engines": { "<engine-name>": { "backend": "...", "note": "...", "url": "https://github.com/..." } },
  "models": [ { ...model... }, { ...model... } ]
}
```

- `engines` — the engine registry. Every engine a model references must exist
  here with a `url` (repo link). The README engine guide is built from this.
  `backend` is one of CUDA, ROCm, Metal, CPU or several joined with ` / ` in
  the canonical order CUDA, ROCm, CPU, Metal (e.g. `CUDA / ROCm / CPU / Metal`).
- `models` — the list of models. **No duplicates.**

## Model object contract

Each entry in `models` has exactly this shape:

```json
{
  "id": "bonsai-2-27b",
  "name": "Bonsai 2 27B",
  "full_name": "Ternary-Bonsai-2-27B",
  "type": "LLM (ternary)",
  "formats": [
    { "name": "GGUF", "hf": "prism-ml/Ternary-Bonsai-2-27B-gguf" },
    { "name": "MLX", "hf": "prism-ml/Ternary-Bonsai-2-27B-gguf" }
  ],
  "license": "Apache 2.0",
  "params": "27B",
  "hf": "prism-ml/Ternary-Bonsai-2-27B-gguf",
  "vram_tier": "12GB",
  "vram_min": "8GB",
  "backends": ["CUDA", "Metal", "CPU", "ROCm"],
  "supported_engines": ["llama.cpp", "MLX-fast (Bonsai 2)"],
  "engines": [
    {
      "engine": "llama.cpp",
      "tps": "67-71",
      "hardware": "RTX 5060 Ti 16GB",
      "quant": "MTP head",
      "date": "2026-09-27",
      "source_post": "https://lightbrd.com/sudoingX"
    }
  ],
  "why": "One-line reason people love it.",
  "engagement": { "likes": 2750, "comments": 640, "views": 84563, "last_7d_likes": 1420 },
  "last_seen": "2026-09-27"
}
```

### Field meanings

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Unique slug. **No duplicates.** |
| `name` | yes | Short display name. **No duplicates.** |
| `full_name` | yes | Full model name. |
| `type` | yes | Model type (LLM, LLM (ternary), MoE, etc.). |
| `formats` | yes | Weight formats, **each `{ name, hf }` with its own Hugging Face link**. One entry per format. |
| `license` | yes | License. |
| `params` | yes | Parameter count (total / active for MoE). |
| `hf` | yes | Primary Hugging Face repo id → `https://huggingface.co/<hf>`. |
| `vram_tier` | yes | VRAM category (8GB, 12GB, 16GB, 24GB, 32GB, 48GB). **A label, not a requirement**: the README publishes the least amount needed (`vram_min`), never this string — they disagreed for 20 of 46 models, and 9 values in the store (`CPU`, `48`, `8`, `6GB`, `9GB`, `18GB`, `2GB`, `128GB`, `512GB`) sit outside the documented list (issue #337). |
| `vram_min` | yes | **LEAST required VRAM** needed to run the model (e.g. 8GB) — the number the README most-loved `VRAM` column publishes. Community-reported from the X measurement posts; cross-checked against the smallest usable quant file size on Hugging Face (HF does not expose a VRAM field — see note below). |
| `system_ram_min` | no | **System RAM / unified-memory requirement**, only when a source post states it (e.g. `16GB`). The CPU and Metal tables are RAM-bound (Apple Silicon is unified memory) and partial offload keeps the un-offloaded layers + KV cache in system RAM. Never derived from `vram_min` and never invented — an absent value is a reported data gap. |
| `weight_gb` | no | **Weight footprint per format + quant** as stated by the post (e.g. `5.95GB Q4_K_M`) — the budget a run needs before any context is allocated. |
| `context_tokens` | no | **Context window** as stated by the post (e.g. `131072`, `128K`). The KV cache scales with it and consumes RAM and VRAM alike. |
| `storage_offload` | no | **Storage-offload requirement** as stated by the post (e.g. `640GB NVMe, experts on SSD`) — MoE engines (Strata) run big models by streaming experts from storage. |
| `engine_min_version` | no | **Engine minimum version / required flags** as stated by the post (e.g. `llama.cpp b6xxx, --n-gpu-layers 99`); many figures only reproduce on a specific build. |
| `backends` | yes | Backends it runs on (CUDA, Metal, CPU, ROCm = AMD GPUs). Must include every backend its measurements render in — ingest adds it (`sync_backends`); AMD hardware (Radeon / RX / Strix Halo / ROCm) is ROCm whatever the engine. |
| `supported_engines` | yes | **List of engines the model is supported by.** Each must have a measurement in `engines`. |
| `engines` | yes | **Per-engine t/s measurements** — the core data. One entry per (engine, date). A measurement may ALSO carry the footprint of that run — `weight_gb`, `context_tokens`, `system_ram_min`, `storage_offload` (all optional, same meanings as above) — because one model's quants fit different cards and the README's card-fit tables are built from the measurement that produced each figure (issue #337). State them only when the post gives them for THAT run. |
| `why` | yes | Why people love it. |
| `engagement` | yes | X engagement: likes, comments, views, last_7d_likes. |
| `last_seen` | yes | Last date the model was seen trending (YYYY-MM-DD). |

### About VRAM / Hugging Face metadata

**Hugging Face does NOT expose a "VRAM required" field.** The model `cardData`
contains only license / name / tags. The HF API *does* return file sizes
(`?blobs=true`) — the **smallest usable quant file size** in the repo is a good
proxy for minimum VRAM (e.g. Bonsai 2's 5.95 GB PTQ1_0 ≈ 8 GB min). We do not
invent a VRAM number: `vram_min` is **community-reported from the X measurement
posts** and cross-checked against HF quant-file sizes. `vram_tier` is the coarse
category for the README tables.

### The `engines` array — t/s per engine

This is the heart of the contract. Each measurement:

```json
{
  "engine": "llama.cpp",
  "tps": "67-71",
  "hardware": "RTX 5060 Ti 16GB",
  "quant": "MTP head",
  "date": "2026-09-27",
  "source_post": "https://lightbrd.com/sudoingX"
}
```

- `engine` — must exist in the top-level `engines` registry (which has its repo `url`).
- `tps` — tokens/sec, always **per engine**. A bare number with no engine is invalid.
- `hardware` — the hardware it was measured on.
- `quant` — quantization.
- `date` — measurement date (YYYY-MM-DD).
- `source_post` — the X post (lightbrd.com) the figure came from.

### Optional model keys (additive, never `required`)

- `engine_aliases` — `{posted engine name: registry engine name}` for a model that
  only runs on a fork of an engine (applied at ingest and every sort).
- `measurement_model_aliases` (issue #652) — a list of **store model ids** whose
  names a measurement on this row may legitimately mention: the *documented
  exception* to the measurement-attribution refusal (a variant row naming its base
  model, a bake-off row naming the model it compares against). It lives here as
  reviewable data — never as a code literal — because a data diff shows a reviewer
  exactly which exceptions were taken, a refresh carries them forward, and
  `check_measurement_alias_map` refuses a counterpart id that is not a model id in
  the store. Ingest (`misattributed_measurement_reason`) reads the incoming row's
  key and the same-id store row's.

## Rules enforced by `scripts/validate.py`

1. **No duplicate models** (by `id` or `name`).
2. **No model removed** vs the previous snapshot.
3. Every model has all required fields + at least one engine measurement with
   engine name + t/s + repo link.
4. `supported_engines` lists engines that each have a measurement.
5. Backend tables sorted by highest t/s descending.
6. **JSON <-> README sync**: every model + engine measurement in the JSON appears
   in the README, and the "Last generated" timestamp matches — both change
   together.
7. Every model in the store appears in the README.
