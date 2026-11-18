# engine-skill-decision-edge0-2903

## Why

The weekly registry sync (#179/#229) registered the upstream engine `edge0`
(andyholst/trending-local-llms `data/models.json`, `.engines["edge0"]`, registered by human decision
2026-11-17) together with its model `edge0-145b`. At writing the vendored `data/models.json` carried
neither (main `f7eb17d02`), so `make check-engine-skill-gap` could not see the gap the tracking issue
#2903 names; #2906's store re-vendor has since landed those records.

The upstream repository's own README, releases and `edge0-strata/EDGE0.md` (read 2026-11-18) say what
serving `edge0-145b` actually requires:

- Edge0 145B/120B run on `edge0-strata`, a fork of Strata, built with CMake + Ninja against CUDA 13
  and a pinned llama.cpp/ggml snapshot (`3cf03257f219afbe7334045ff7c6a06ac68c627d` unpacked into
  `third_party/llama.cpp`), and served by `serve/server.py --engine strata --config <file>`.
- The launch contract (v5) passes a server config whose paths name a model PACK DIRECTORY:
  `--pack ${MODEL_DIR}`, `${MODEL_DIR}/model-skeleton.gguf`, `${MODEL_DIR}/ple-fp8.gguf`,
  `${MODEL_DIR}/profile.bin`, `--mtp ${MODEL_DIR}/mtp`, `tokenizer/${MODEL_DIR}/tokenizer`, and env
  entries `STRATA_LATENT_A=${MODEL_DIR}/experts.bin`, `STRATA_LATENT_LABELS=${MODEL_DIR}/labels.bin`,
  `STRATA_LATENT_DENSE=${DU_FILE}`. The HF checkpoint `Edge0/Edge0-145B-q3k` is exactly such a pack
  (`experts.bin`, `dense.bin`, `labels.bin`, `profile.bin`, `model-skeleton.gguf`, `ple-fp8.gguf`,
  `mtp/`, `tokenizer/`, `model.json`).
- llgenie's model store fetches a quant as one file and the engine launch contract hands the engine a
  single GGUF path (`{model}`); nothing in the repo downloads a multi-file pack directory or starts a
  server from one. The Metal path of `edge0-strata` is macOS-only and cannot run in llgenie's Linux
  images.

So the honest resolution today is the same class as `Janas` (#229, deferred for its own `.jns` model
format): a DATED DECISION in `data/unsupported-engines.json`, plus the model-pack serving gap filed as
its own linked issue. Shipping the engine image is worthless while no model store path can serve the
pack; shipping the skill would claim a launch contract llgenie cannot honour.

## How

1. The upstream records land through #2906's full store re-vendor — its 120-model verbatim copy of
   upstream master already carries `.engines["edge0"]` and the `edge0-145b` entry (verified at head
   `b0417654105ff5c3e75c22957b861e1b276aebfa`: `jq` presence, model count 120). This lane re-confirms
   their presence after rebasing onto it instead of splicing `data/models.json` itself, so the store
   stays single-sourced and additive.
2. Refine the decision entry: #2906's re-vendor wave already carries `"edge0"` in
   `data/unsupported-engines.json` as `decision: deferred`, `issue: 2903` with a registration-generic
   reason; this lane replaces that reason with the upstream-read one (pack-format serving gap #2909,
   CUDA 13, macOS-only Metal) and keeps main's `backend` and `upstream` fields.
3. Re-run every view gate the registry feeds on the rebased branch (`check-engine-skill-gap`,
   `check-trend-list-matrix`, `check-quant-catalog`, `check-vram-scope-view`) so each check gate
   agrees with the registry this change carries; the committed views themselves ride on #2906 and this
   lane does not re-render them.
4. File the out-of-scope work as its own issue — folder-format model-pack serving in the model store
   and launch contract — link it in BOTH directions (`#2903`'s `Not covered` names it; it names
   `#2903`), never as prose.
5. `#2903` closes with this PR (`closes #2903`): the issue's three acceptance criteria become provable
   against the local store.

## Benefits

- `edge0` stops being an unresolved gap: `make check-engine-skill-gap` and `skills-validate` pass
  against the vendored store, and the omission is a decision with a date and an upstream-read reason.
- The vendored store matches upstream for the records the weekly sync was already carrying, so #2903's
  acceptance is checkable here rather than next week.
- The real blocker — serving multi-file model packs — becomes a first-class, linkable work item
  instead of an untracked footnote.
