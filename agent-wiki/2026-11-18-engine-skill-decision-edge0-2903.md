# 2026-11-18 — engine-skill-decision-edge0-2903 (issue #2903, PR #<TBD>)

`edge0` (upstream engine registered 2026-11-17, issue #988 lineage) is resolved as a **dated
decision**, not a skill: `data/unsupported-engines.json` now carries `edge0` with
`decision: deferred`, `decided: 2026-11-18`, `issue: 2903`, and a reason read from the upstream
repository itself. The serving blocker it names — llgenie cannot fetch or launch multi-file model
packs — was filed as its own issue #2909, linked in both directions.

## What was verified

- **Upstream anatomy** (`Edge0-AI/Edge0`, read 2026-11-18): `edge0-145b` is served by
  `edge0-strata`, a Strata fork built with CMake + CUDA 13 against a pinned ggml snapshot
  (`3cf03257f219afbe7334045ff7c6a06ac68c627d`); `edge0-strata/EDGE0.md` launch contract v5 + the
  `edge0/models/edge0-145b.json` config template wire `${MODEL_DIR}/model-skeleton.gguf`,
  `ple-fp8.gguf`, `profile.bin`, `--pack ${MODEL_DIR}`, `--mtp ${MODEL_DIR}/mtp`,
  `tokenizer/${MODEL_DIR}/tokenizer`, `STRATA_LATENT_A=${MODEL_DIR}/experts.bin`,
  `STRATA_LATENT_LABELS=${MODEL_DIR}/labels.bin`. The HF checkpoint `Edge0/Edge0-145B-q3k` is exactly
  that pack (24-entry tree: `experts.bin`, `dense.bin`, `labels.bin`, `profile.bin`,
  `model-skeleton.gguf`, `ple-fp8.gguf`, `mtp/`, `tokenizer/`, `model.json`, …; tree API measured
  2026-11-18). Metal backend is macOS-only per the README platform table.
- **llgenie's contract** (measured at main `f7eb17d02`): `make run-engine` passes one model argument
  (`MODEL=<path | HF id>`, `mk/engines.mk:350-352`) and `scripts/hf_download.py:4` is a one-file
  per-quant downloader (whole-repo mode `-` exists at `:9,:33` but no engine param drives a
  manifest-based pack fetch). A pack-format model therefore has no store or launch path today.
- **Gate proof**: `make check-engine-skill-gap` exits 0 naming 50 registry engines,
  known-unsupported 33, **unresolved 0** — `edge0` covered by the refined decision entry (measured on
  the rebased branch after `render-engine-skill-gap`).
- **Registry carriage**: the upstream `edge0` + `edge0-145b` records landed via #2906's 120-model
  verbatim re-vendor (merged as `df6a18baa`), together with a thin `edge0` deferred entry. This lane
  refines that entry's reason to the upstream-read text (and `render-engine-skill-gap` re-derives the
  committed gap view from it), so the store stays single-sourced and additive.

## Key decisions

- Decision path (the `Janas` precedent, #229, deferred for its `.jns` format) over shipping an
  engine image that could never serve its only listed model; shipping the skill would advertise a
  launch contract llgenie cannot honour.
- Out-of-scope work is issue #2909 (manifest-driven pack fetch + directory launch + file-set size
  gating), never prose: #2903's `Not covered` names #2909, #2909 names #2903 as its origin.
  The `edge0` decision is revisited when #2909 lands.

## Current status

Rebased onto `df6a18baa` (#2906's re-vendor); decision refinement + gap-view re-render + linked issue
#2909 landed on the branch; `check-engine-skill-gap` green with 0 unresolved. `#2903` closes when
PR #2910 merges.
