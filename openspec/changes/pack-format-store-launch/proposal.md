# Pack-format store + launch path: multi-file checkpoints fetchable and servable

## Why

Measured on main `f7eb17d028da213fad321915be62cec485e19eb7` (2026-11-18, this change's
`AGENTS:` — exactly the `origin/main` `make bot-preflight` measured): the model store and
the engine launch contract have **no path for a multi-file "pack" checkpoint**. Every
engine param (`containers/engines/params/*.json`) is a single-model-file contract; `make
run-engine` passes exactly one model argument (`mk/engines.mk:350-352` →
`scripts/engine_image.py run --model`); and the downloader contract is one file per quant
unit (`scripts/hf_download.py` `<repo> <filename> <dest_dir> <label>`, with only a
whole-repo snapshot mode). A checkpoint that an engine consumes as a DIRECTORY of named
parts — e.g. an `experts.bin` / `dense.bin` / `model-skeleton.gguf` / `mtp/` tree whose
launch wires `${MODEL_DIR}/model-skeleton.gguf`, `--pack ${MODEL_DIR}`, `--mtp
${MODEL_DIR}/mtp`, `tokenizer/${MODEL_DIR}/tokenizer` and `STRATA_LATENT_A=${MODEL_DIR}/
experts.bin` into one engine config — cannot be fetched or served. The hit model:
`edge0` (upstream human registration 2026-11-17, measured 12.9 t/s decode on an RTX 5060
Ti 16GB), whose checkpoint `Edge0/Edge0-145B-q3k` is a 24-entry pack tree (measured
2026-11-18 from the Hub tree API).

Correction on the vendored data: the issue-under-test originally claimed the vendored
registry already carried `edge0-145b` (`formats[0].name = "Edge0-145B"`). Re-measured on
this exact main, `data/models.json` (118 rows), `data/unsupported-engines.json`,
`data/trending-quant-catalog.json` and `data/strata_models.json` contain **no** `edge0`,
`Edge0` or `145b` reference (grep + json count both 0), and `make check-engine-skill-gap`
reports `unresolved 0`, `shipped 17`, `known-unsupported 29`. So there is no `edge0`
registry row to ship a skill for and no date-stamped `edge0` decision to re-record in
`unsupported-engines.json` today — the engine is simply not in the vendored store yet.
What **is** actionable and testable is the generalized pack-format capability: the store's
manifest-driven multi-file fetch, the whole-file-set VRAM gating, and the launch-contract
pack-config seam that `edge0` (or any future pack row) needs the moment it enters the
registry. That is what this change ships, hermetically proven; the sub-text of
`unsupported-engines.json`'s note ("an engine with no skill must be a DECISION") is
revisited in the wiki entry for this change with this measured absence named.

## What Changes

- **Model store: manifest-driven pack fetch.** `scripts/hf_download.py` gains a pack
  MANIFEST mode: a `<filename>` that is an existing `.json` path names the checkpoint's
  file set (`{"files": [...]}` or a bare array). Every named file is fetched into ONE
  destination directory through the same single-file path (resume, stall-watch, 429-wait,
  retry, refresh); a pack is "present" only when EVERY named file is on disk, and a
  partial set resumes instead of passing as complete. Same CLI, no second downloader.
- **Pack-aware planning + download.** `scripts/model_engine_pick.py` reads a `formats[]`
  entry that carries a `files` list as a pack declaration (`pack_manifest`); plans it as a
  whole-directory download sized by the SUM of its files (`pack_plan`), refuses a set of
  which any file is missing on the Hub, and routes the download through the existing
  single-file path back into the pack directory.
- **Whole-file-set card/VRAM gating.** A pack model's stated budget is the whole file set
  (`pack_weight_gb`), not one file; `stated_budget_gb` reads it, so `fits` / `card_evidence`
  admit or refuse a pack as a set. `vram_scope_view` is a pure function of the vendored
  registry and stays byte-identical (no pack row exists to re-render).
- **Launch-contract pack-config seam.** `write_pack_config(model_dir, layout)` writes
  `<model_dir>/llgenie-pack-config.json` wiring the engine's declared named parts (`model`,
  `ple`, `profile`, `labels`, `mtp`...) to their absolute paths. `download()` calls it
  when the plan is a pack. The engine's launch — whether that is `edge0`'s skill when it
  ships, or any engine whose params declare a `pack` layout — reads that one file instead
  of re-inventing the parts.

## Capabilities

- **pack-fetch**: the model store fetches a multi-file checkpoint as one pack directory
  from a file manifest, resumably.
- **pack-plan**: pack downloads are planned and downloaded as whole file sets.
- **pack-gate**: card/VRAM gating sizes a pack by the whole file set.
- **pack-launch**: the launch contract resolves `MODEL=` to a pack directory and wires the
  named parts into one engine config file.

## Impact

No existing behavior changes: a model with no `files`-carrying format entry is untouched
(`pack_manifest` returns None), and `data/models.json` is not edited. The new paths are
additive; every new function is covered by hermetic tests that run under `make test-unit`.

The two hardware/live acceptance halves that cannot run on this agent host are, per the
issue, recorded in the wiki entry: the `make test-engine-host` serve proof needs a real
pack-format model on a real GPU and a shipping `edge0` skill (explicitly "Not covered" by
this issue), and the `edge0` decision revisit needs the engine to have entered the
vendored registry first — which `make check-engine-skill-gap` measures (currently
`unresolved 0`).
