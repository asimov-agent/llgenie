## 1. Ranking

- [x] 1.1 `scripts/model_engine_pick.py`: `rank_engines` (image variant for this host, t/s then engagement, Apple-Silicon rows ignored) and `rank_models` (fits the card, has a runnable engine).
- [x] 1.2 Unit tests against the pinned registry fixture.

## 2. llgenie flags

- [x] 2.1 `--pick`, `--engine`, `--auto` in `scripts/llama_serve.py`; prompt only on a terminal; `--engine` narrows the models to those the engine can run.
- [x] 2.2 Serve through `~/bin/llgenie-engine-<id>` on `127.0.0.1:<port>/v1` (`llm-local`); plain local GGUF flow unchanged.

## 3. Download

- [x] 3.1 Reuse a matching file under `~/models`; else pick the largest GGUF that leaves ~15% of the card free and download it with `scripts/hf_download.py`.
- [x] 3.2 `LLGENIE_DOWNLOAD_MAX_BYTES` ranged-chunk download; CI test fetches 1 MiB of a real Hub GGUF and checks the GGUF magic (runs in `make test-unit`).

## 4. Verify

- [x] 4.1 `make test-unit`, `make lint`, `make openspec-validate NAME=feat-model-engine-pick`.
- [x] 4.2 Local: `make install`, then `llgenie --pick` with models from `~/models` and an engine of choice answers on `/v1`.
