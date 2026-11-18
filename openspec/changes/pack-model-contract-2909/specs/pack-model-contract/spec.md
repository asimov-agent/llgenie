# Pack model contract — multi-file model checkpoints as one manifest-gated unit

## ADDED Requirements

### Requirement: a registry formats entry may declare a pack manifest, validated at the door

A `formats[]` record may carry a `pack` member — `{repo, revision?, files: [{path, bytes?}]}` —
declaring the WHOLE multi-file checkpoint directory (`path` may nest). The vendored normaliser
(`scripts/sync_registry.py::normalise_formats`) passes a well-formed pack through unchanged and
drops a malformed manifest with a named sync note; `scripts/pack_contract.manifest` refuses a
manifest that is not a non-empty list of repo-relative file paths (no absolute paths, no empty
paths), so a half manifest never resolves into a fetch plan. `data/models.json` keeps its current
shape: the pack is ADDITIVE — records without it resolve, size, fetch, and serve exactly as before.

#### Scenario: a well-formed pack survives the vendored normaliser

Given a trending row whose GGUF entry carries `pack: {files: [{path: "a.bin", bytes: 1}]}`
When `scripts/sync_registry.py::normalise_formats` runs
Then the entry keeps its `pack` member byte-for-byte and the sync note stays empty

#### Scenario: a malformed manifest is refused before any byte

Given a manifest whose `files` is empty or names an absolute path
When `scripts/pack_contract.manifest` resolves it, or `hf_download.py` is invoked on it, or the
vendored normaliser reads it
Then it resolves to `None` / exits 2 / drops the pack with a named note — and the downloader is
never invoked on it

### Requirement: a pack is sized and gated by the sum of its declared bytes

The fetch budget for a pack is the SUM of its manifest's declared bytes: `pack_contract.pack_gb`
feeds `stated_budget_gb` (measurement footprint first, then the pack sum, then the model's stated
`weight_gb`), and `plan_download` returns no plan unless the WHOLE file set fits the host budget —
there is no partial-pack plan, because the manifest is atomic.

#### Scenario: the manifest byte sum is the plan size

Given a pack whose four files declare 100 bytes each
When `plan_download` builds its plan
Then `plan["size"] == 400`, `plan["pack"] is True`, `plan["dir"] is True`, and `plan["files"]`
lists every declared path in manifest order

#### Scenario: a pack that does not fit is refused whole

Given a host budget below the manifest byte sum
When `plan_download` runs
Then it returns no plan (no partial-pack fetch exists)

### Requirement: the whole pack is fetched by hf_download's manifest mode, resumably

`scripts/hf_download.py` accepts a filename of `@<manifest.json>`: the ONE resumable download leg
fetches every declared file of the pack into `~/models/<org>__<repo>/` in a single call, with the
same retry/stall/exit contract as a single file (0 completed, 1 incomplete, 2 invalid args).
A part whose on-disk size differs from its declared `bytes` counts as NOT present.
`scripts/model_engine_pick.py::download` writes the manifest as a `<model-id>.pack.json` sidecar
and invokes that leg ONCE — there is no per-part or whole-repo loop of its own.

#### Scenario: a crash leaves a partial pack and the next run continues it

Given a manifest download that crashed with some declared parts on disk
When `hf_download.py <repo> @<manifest.json> <dir> <label>` runs again
Then only the missing/mis-sized parts are fetched, completed parts are not re-fetched, and the run
exits 0 with every declared part at its declared size

#### Scenario: a completed pack is not fetched again

Given every declared part present at its declared size
When the manifest mode runs again
Then the downloader binary is never invoked and the exit is 0

### Requirement: a pack is launched only with every declared part bound, from params

Frozen engine params declare pack serving with `model_contract: "pack"` plus a variant's
`pack: {parts, config_env}`; `scripts/engine_skills.py` carries both from the variant into the
built run spec (frozen params remain the launch truth) and into the variant digest inputs, so a
pack contract cannot be changed without re-publishing params. At launch,
`scripts/pack_contract.launch_env` verifies EVERY declared part exists under the pack directory
and binds `config_env` as docker `-e VAR=/models/<pack-dir>/<part>` pairs; a missing part, a
non-directory model, or a `model_contract` without declared parts refuses the run, naming what is
missing. Engines that do not declare the contract see unchanged specs and digests.

#### Scenario: the launch binds exactly the declared wiring

Given a pack directory containing every declared part and `config_env` entries for the pack
directory (`.`) and two parts
When `launch_env` builds the engine wiring
Then the env list is exactly `-e VAR=/models/<pack-dir>[/<part>]` pairs for those entries

#### Scenario: a half pack never launches

Given a pack directory missing one declared part
When `launch_env` runs
Then the launch is refused and the refusal names the missing part

#### Scenario: non-pack engines are untouched

Given frozen params whose variants declare no `model_contract`
When `image_spec` builds any variant spec
Then no `model_contract`/`pack` key appears in the spec and the variant digest is unchanged
