# 2026-11-18 — pack model contract: multi-file checkpoints as one manifest-gated unit (#2909)

## What was verified against the spec

OpenSpec change `pack-model-contract-2909` (proposal + `specs/pack-model-contract/spec.md` +
tasks), `make openspec-validate NAME=pack-model-contract-2909` rc=0. Four requirements, each with
scenarios: (1) `formats[].pack` manifests validated at the door (vendored normaliser passes a
well-formed manifest unchanged, drops a malformed one with a named note); (2) the fetch budget is
the SUM of manifest bytes and the plan is atomic (no partial-pack plan); (3) `hf_download.py`'s
manifest mode (`@<manifest.json>`) fetches the whole file set in one resumable call — completed
parts are not re-fetched, mis-sized parts re-download, a completed pack never invokes the binary;
(4) launch binds only declared parts: frozen params `model_contract: "pack"` + variant
`pack: {parts, config_env}` carried through `scripts/engine_skills.py` into the spec AND the variant
digest inputs, `pack_contract.launch_env` verifies every part and builds the
`-e VAR=/models/<pack-dir>/<part>` wiring, and a half pack is refused naming what is missing.
Non-declaring engines keep unchanged specs and digests.

`tests/test_pack_model_contract.py` — 11 hermetic tests (fake downloader fixtures, no network; the
plan test installs the `_tree` substitute for the #1000 hub-pin guard): manifest shape/rejections,
byte-sum sizing + `stated_budget_gb` order (footprint → pack sum → stated `weight_gb`), plan
atomicity + fits-budget refusal, crash→resume→no-refetch→size re-verify, `download()` routing
through the manifest sidecar in ONE downloader call, launch wiring bind/refusal naming the missing
part, params carry-through only for declaring variants, pack directory local resolution
(`model.json` counts), sync door pass-through/drop. `make check-package-layers` OK with
`pack_contract` in the Product path group. `make render-engine-skill-gap` re-rendered
`data/engine-skill-gap.json` after the edge0 decision re-record.

## Key decisions

- **Manifest mode over snapshot mode**: snapshot (`-`) cannot gate declared sizes nor resume
  size-checked; `@<manifest.json>` reuses the one-file retry/stall/exit contract for a whole file
  set. Snapshot stays for the whole-tree fallback path.
- **The manifest is atomic**: sizing, planning, fetching, and launching all key on the WHOLE
  declared set — a pack that does not fit, or that is missing a part at launch, is refused whole.
  Half a pack is never a serveable model.
- **Params remain the launch truth**: the contract rides frozen params
  (`model_contract`/`pack.parts`/`config_env`) through the digest inputs, so changing the wiring
  re-publishes the engine image tag. `data/models.json` itself stays byte-identical — upstream
  trend rows carry no `pack` member yet; the door is ready for when they do.
- **edge0 stays deferred, honestly re-recorded**: `data/unsupported-engines.json` now states the
  pack gap is CLOSED by #2909 and names what still blocks the engine itself (device-native runtime
  — Linux CUDA needs CUDA 13 — and a measurement we cannot take here). Shipping edge0 params +
  Dockerfile + skill + the host serve proof is its own linked issue filed from this change's
  `Not covered`.

## Current status

Implemented on `feat/pack-model-contract-2909` (the PR for #2909); the full unit suite re-run on
the committed tree and the CI lane verdicts are recorded on the issue/PR. The host serve proof over
a real pack-format model waits on the edge0-shipping issue (gated on explicit human permission to
start inference engines).
