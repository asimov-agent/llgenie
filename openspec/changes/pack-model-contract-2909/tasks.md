# Tasks — pack-model-contract-2909

- [x] `scripts/pack_contract.py`: `manifest` (validated `formats[].pack`), `pack_gb` (byte-sum
      size), `write_manifest` (sidecar for the resumable leg), `launch_env` (validate every part,
      build `-e` wiring), `valid_files` (door validation shared with sync)
- [x] `scripts/hf_download.py` manifest mode: `@<manifest.json>` filename — one resumable call for
      the whole file set, declared-`bytes` presence check, malformed manifest → exit 2
- [x] `scripts/model_engine_pick.py`: pack branch in `plan_download` (whole-set budget, atomic),
      pack byte-sum in `stated_budget_gb`, pack route in `download` (manifest sidecar + one
      `hf_download` invocation), `model.json` as a directory hit in `resolve_local`
- [x] `scripts/engine_skills.py`: `model_contract`/`pack` carried from the skill manifest into
      `render_variant` and `image_spec` (digest inputs); non-declaring engines unchanged
- [x] `scripts/engine_image.py`: `run()` appends `pack_contract.launch_env` for a
      `model_contract == "pack"` spec
- [x] `scripts/sync_registry.py::normalise_formats`: pack pass-through + malformed-manifest drop
      with a named note
- [x] `scripts/package-layers.json`: `pack_contract` placed in the Product group
- [x] `data/unsupported-engines.json`: the edge0 decision record states the pack gap is closed by
      #2909 and names what still blocks the engine itself
- [x] `tests/test_pack_model_contract.py`: hermetic pack fixtures — manifest shape/rejections,
      byte-sum sizing + `stated_budget_gb` order, plan atomicity, crash→resume→no-refetch→size
      re-verify, `download()` routing through the manifest sidecar, launch wiring binding/refusal
      naming the missing part, params carry-through only for declaring variants, pack-directory
      local resolution, sync pass-through/drop
- [x] full unit suite green (`make test-unit`) and lane preflight green (`make lane-preflight`)
