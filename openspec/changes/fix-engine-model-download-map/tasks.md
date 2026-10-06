## 1. Strata's own model map

- [x] 1.1 `scripts/strata_models.py` imports `setup.py` at the skill's pinned commit; `data/strata_models.json` written in setup's order.
- [x] 1.2 `make sync-strata-models` / `make check-strata-models`; `check-strata-models` in the CI `unit` job.

## 2. Plan and download

- [x] 2.1 `strata_serves` / `strata_choice` / `strata_files` / `strata_plan` / `strata_local` in `scripts/model_engine_pick.py`; the hand-copied quant heuristic is removed.
- [x] 2.2 `offer()` gives Strata its own plan and local copy; `engine_plan` / `engine_local` helpers.
- [x] 2.3 `llama_serve._main_pick` downloads the chosen engine's plan; `--dry` lists every shard; `[local]` follows the top engine's copy.
- [x] 2.4 `download(plan=)` passes the revision; `hf_download.py` adds `--revision` from `HF_REVISION`; the byte-capped CI path fetches every shard at the revision.

## 3. Engine start

- [x] 3.1 Strata `pre_launch` passes `--family/--model` from `setup.gguf_choice(first shard)` and refuses other files; params regenerated (`make check-engine-params` clean).

## 4. Tests

- [x] 4.1 `tests/test_strata_download.py` (real setup.py at the pinned commit, live Hub, real hf downloader, pty), in `make test-unit`; watched it fail on main.
- [x] 4.2 `tests/test_trend_pick.py` updated to the per-engine plan (Strata's own plan on an 8 GB RAM host).
- [x] 4.3 `make test-unit`, `make lint`, `make check-strata-models`, `make check-engine-params` and `make openspec-validate NAME=fix-engine-model-download-map` pass.
