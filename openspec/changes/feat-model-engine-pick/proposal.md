# llgenie picks the model and the fastest compatible inference server (issues #93, #94, #95)

## Why

`llgenie` only lists local GGUF files and always serves them with llama-server. Since
#98 every inference server runs from its container image, and the trending-local-llms
registry reports measured t/s per model and engine. A user should be able to say which
model and which engine to use, or let llgenie choose the fastest pair that runs on this
card, and get the model downloaded when it is missing.

Parent: #92. Implements #93 (models that fit this card), #94 (engines that can run the
picked model + engine picker) and #95 (download the picked model). Builds on #98
(engine images + `~/bin/llgenie-engine-<id>` start scripts from `make install`).

## What Changes

- New `scripts/model_engine_pick.py` (stdlib only):
  - `rank_models()`: registry models that fit the card (`vram_tier` <= card RAM) and
    have at least one engine with an image for this host, best reported t/s first.
  - `rank_engines(model)`: the engines that can run the model here (image variant for
    the host backend, cpu fallback), highest t/s first, ties broken by trending
    engagement. Apple-Silicon measurements are ignored for container hosts.
  - `resolve_local(model)`: the matching file under `~/models`, if any.
  - `download(model)`: picks the largest GGUF that leaves ~15% of the card free and
    fetches it with the existing `scripts/hf_download.py`.
    `LLGENIE_DOWNLOAD_MAX_BYTES=N` fetches only the first N bytes (HTTP Range); CI uses
    this to test the real download path with a small chunk.
- `llgenie` (`scripts/llama_serve.py`) gains `--pick`, `--engine <name>` and `--auto`:
  - `llgenie --pick` lists the models that fit, each with its fastest engine, and asks.
  - `llgenie --pick <model>` / `llgenie --engine <engine>` take them as parameters.
  - `--auto` (and any non-interactive run) never asks: top model, top engine.
  - A missing model is downloaded into `~/models` first.
  - The model is served through `~/bin/llgenie-engine-<id>` (the engine image), on
    `127.0.0.1:<port>/v1` as `llm-local`.
- The plain `llgenie` / `llgenie <substring>` flow for local GGUF files is unchanged.

## Impact

- New: `scripts/model_engine_pick.py`, `tests/test_model_engine_pick.py`.
- Changed: `scripts/llama_serve.py` (new flags), `Makefile` (`test-unit` runs the new tests).
