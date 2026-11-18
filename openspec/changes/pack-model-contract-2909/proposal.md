# Proposal: pack-model-contract-2909

## Why

The registry model `edge0-145b` ships as a multi-file PACK (HF checkpoint
`Edge0/Edge0-145B-q3k`, a 24-entry tree consumed as a DIRECTORY), and llgenie has no path for that
shape: `make run-engine` passes exactly one model argument (`mk/engines.mk` `run-engine` →
`scripts/engine_image.py run --model`), the downloader contract is one file per quant unit
(`scripts/hf_download.py:4`, whole-repo mode `-` at `:33` exists but no manifest mode), and every
engine params file is a single-model-file contract. Measured at main `0a2a7f326`: the vendored
record `.models[id="edge0-145b"].formats[0]` is one pseudo-quant `GGUF` entry with no file field.
Issue #2909 (filed from the engine-skill decision lane that closed as PR #2910) carries the full
problem/fix/gate text.

## What Changes

1. **Pack fetch (model store):** `scripts/hf_download.py` gains a MANIFEST mode — the filename
   slot accepts `@<manifest.json>` naming a file list (`{"revision": …, "files": [{"path",
   "bytes"}]}`); the download runs `hf download <repo> <file>… --local-dir <dest>` over exactly
   those files, keeping the one downloader's resume/retry/stall-watch/throttle/Xet-fallback rules,
   and "present" means EVERY manifest file exists with its expected size (resumable per file).
   `scripts/model_engine_pick.py download()` routes a pack model through the manifest mode,
   generating the manifest from the registry record (2).
2. **Registry (ADDITIVE only):** a `formats[]` entry MAY carry `pack: {"revision": …, "files":
   [{"path", "bytes"}]}` — the pack contract rides the existing formats array; entries without it
   stay single-quant entries. `scripts/registry_sync.py` normalise keeps the field on pass-through.
3. **Launch contract:** engine params gain `model_contract` — `"file"` (default for every current
   engine, never written explicitly) or `"pack"` with `pack.parts` (named paths relative to the
   pack dir) + `config_env` templates mapping each part to an env var (the edge0 v5 shape:
   `STRATA_MODEL_DIR`, `STRATA_LATENT_A`, … and the `--pack`/`--mtp`/`tokenizer` argv wiring the
   skill's serve template composes). `scripts/engine_image.py run --model <dir>` resolves a pack
   directory: validates every declared part is on disk (else refuses, naming the missing part),
   passes the dir as `LLGENIE_MODEL` plus the wired env vars, and mounts `/models` unchanged.
4. **Size gating:** `scripts/model_engine_pick.py` computes `pack_bytes(model)` (sum of the
   declared pack file bytes) and the card/VRAM fit + `scope_vram_gb`/`model_in_scope` view use the
   whole file set for pack records, never a single quant.
5. **Decision re-record (AC4, re-record branch):** `data/unsupported-engines.json`'s `edge0` entry
   is re-recorded with a dated reason naming the landed pack contract (this change) and the
   remaining gate (host serve proof on a pack model, which is blocked on human serve permission
   per the host rule, and on shipping the edge0 engine itself).

## Impact

- Affected specs: `model-pack-serving` (new capability)
- Affected code: `scripts/hf_download.py`, `scripts/model_engine_pick.py`, `scripts/engine_image.py`,
  `scripts/registry_sync.py` (normalise pass-through), `scripts/engine_skills.py` + params generator
  (only when an engine skill declares a pack contract), `data/unsupported-engines.json`
- Affected tests: new `tests/test_pack_model_contract.py` (hermetic, synthetic pack fixture);
  updates in `tests/test_model_engine_pick.py` / vram-scope fixtures where a pack record is added

## Not covered (filed as a separate linked issue)

- The HOST serve proof `make test-engine-host` on a pack-format model and shipping the edge0
  engine itself (Dockerfile/params/skill): chained on the human-permission gate for starting
  inference servers on this host. Filed as its own issue, named in both directions.
