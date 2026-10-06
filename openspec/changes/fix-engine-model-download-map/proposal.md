# llgenie: Strata downloads exactly the GGUF files Strata's setup.py names

## Why

On a 16 GB RTX 4090 + 62 GB RAM host, interactive `llgenie` -> 1 (Qwen3.8-Flash-Next 125B) ->
1 (Strata) started downloading `unsloth/Qwen3.8-Flash-Next-GGUF` `UD-IQ1_M` (3 shards, 75 GB).
Strata v0.1.39 cannot run that file: its `setup.py` (`MODELS` / `FAMILIES`) only accepts
ISTA-DASLab's GSQ-RCO files (Q2_0, IQ2_XS, IQ3_XXS, IQ3_S; the Coder's IQ1_M; Swift 1.5's) and
Unsloth's UD-IQ4_XS / UD-Q4_K_XL, and `gguf_unsupported()` refuses everything else. Defects:

1. `llama_serve._main_pick` downloads with `mp.download(model, gb, fmt=fmt)`: the chosen engine
   is dropped, so the download re-plans with the generic "largest GGUF that fits" rule and
   fetches another file than the list planned and Strata reads.
2. `offer()` keeps one plan per format (the top engine's), so another engine of the same format
   shared Strata's plan, and Strata's plan was a heuristic (the smallest file whose quant token
   is in a hand-copied list), not Strata's own mapping.
3. The Strata `pre_launch` never told setup which choice the files are (`--family` / `--model`),
   so setup would look for its own default size's file names in the folder.

Several GGUF files per model are expected: every Strata choice is published split (GSQ-RCO: 2
shards, UD-IQ4_XS: 3, UD-Q4_K_XL: 4). The problem was WHICH files.

## What Changes

- `data/strata_models.json`: Strata's model map, imported from `setup.py` at the skill's pinned
  commit (`MODELS`, `FAMILIES` split into repo / pinned revision / subfolder, `HF_REVISIONS`), in
  setup's own order. `make sync-strata-models` writes it; `make check-strata-models` (CI `unit`
  job) fails when it differs from the pinned `setup.py`.
- Model name -> Strata's files: the registry model whose Hub name is in Strata's default family
  repo (`Qwen/Qwen3.8-Flash-Next`) is Strata's model. Its choice is what `setup.py --yes` installs:
  the first family (`qwen`), `IQ3_XXS` from 60 GB of RAM, else the first size (`Q2_0`). The plan is
  every shard of that choice (`model_file` / `model_shards`) from its repo at its pinned revision.
- `offer()` gives Strata its own plan and local copy (`engine_plans` / `engine_local`); other
  engines keep their existing per-format plan. `llama_serve._main_pick` downloads the chosen
  engine's plan, the one the list showed. `--dry` lists every shard.
- The hf downloader fetches at the plan's revision (`HF_REVISION` -> `hf download --revision`).
- A local copy is reused for Strata only when a complete shard set of a Strata choice is present.
- Strata `pre_launch` passes setup the choice the files are, from Strata's own
  `gguf_choice(<first shard>)`, as `--family F --model M` next to `--gguf-dir`, and stops with a
  clear error for a file Strata cannot run.

## Impact

- `scripts/model_engine_pick.py`, `scripts/llama_serve.py`, `scripts/hf_download.py`,
  `scripts/strata_models.py` (new), `data/strata_models.json` (new),
  `skills/engines/strata/SKILL.md` + regenerated `containers/engines/params/strata.json`,
  `Makefile`, CI `unit` job, `tests/test_strata_download.py` (new), `tests/test_trend_pick.py`.
- No change to the files chosen for any other engine.

Issue: #108. Related: #105 / PR #106.
