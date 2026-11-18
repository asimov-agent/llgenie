# pack-format-store-launch — spec of record

## ADDED Requirements

### Requirement: the model store fetches a multi-file checkpoint from a file manifest
The model store SHALL fetch a multi-file "pack" checkpoint as ONE pack directory from its
file manifest: `scripts/hf_download.py` SHALL accept an existing `.json` path in the
filename position whose content is `{"files": [<repo paths>]}` or a bare JSON array, SHALL
fetch every named file into the ONE destination directory through the same single-file
download path (resume, stall-watch, 429-wait, retry, refresh), and SHALL report the pack
"present"/complete only when EVERY named file is on disk — a partial set SHALL resume, never
pass as complete. (OpenSpec pack-format-store-launch, the `edge0-145b`-style checkpoint.)

#### Scenario: every named file lands in one pack directory
- **Given** a pack manifest naming several files of a multi-file checkpoint,
- **When**  `hf_download.py` fetches it (a real fake-`hf` writes the named files),
- **Then**  every named file is on disk in the ONE destination directory,
- **And**   the download logs a `PACK COMPLETE N/N files` line.
- **Test:** `tests/test_hf_download_pack.py::test_pack_manifest_fetches_every_named_file_into_one_dir`

#### Scenario: a partial pack resumes
- **Given** a pack whose manifest names 4 files and 2 are already on disk,
- **When**  `hf_download.py` runs again,
- **Then**  the 2 missing files are fetched without re-downloading the complete ones,
- **And**   every named file is present afterward.
- **Test:** `tests/test_hf_download_pack.py::test_partial_pack_resumes_not_redownloads_complete_files`

#### Scenario: a bare array manifest is accepted
- **Given** a pack manifest written as a plain JSON array of file paths,
- **When**  `hf_download.py` fetches it,
- **Then**  every named file lands in the destination directory.
- **Test:** `tests/test_hf_download_pack.py::test_pack_manifest_bare_array_form_is_accepted`

### Requirement: pack downloads are planned and downloaded as whole file sets
The model store SHALL plan a pack-format checkpoint (a `formats[]` entry carrying a `files`
list) as a whole-directory download (`plan["dir"] = True`, `path == ""`, `files` = the named
set, `size` = the SUM of every file's bytes), SHALL refuse the plan when ANY named file is
missing on the Hub, and SHALL route the download through the existing single-file path back
into the pack directory. A model with no `files`-carrying format entry is not a pack and is
untouched.

#### Scenario: a pack's size is the sum of the file set
- **Given** a pack model whose Hub files sum to 20 GB (largest single file 8 GB),
- **When**  the pack is planned within a 15 GB card budget,
- **Then**  there is no plan (the WHOLE 20 GB set must fit),
- **And**   within a 24 GB budget the plan carries the whole-set sum as its size.
- **Test:** `tests/test_pack_format.py::test_pack_plan_sizes_by_the_whole_file_set`

#### Scenario: a pack with a missing file is not servable
- **Given** a pack whose Hub tree lacks one manifest file,
- **When**  the pack is planned on a budget that would fit the present files,
- **Then**  there is no plan (a partial checkout is not a servable checkpoint).
- **Test:** `tests/test_pack_format.py::test_pack_plan_refuses_when_a_named_file_is_missing`

#### Scenario: plan_download returns a pack plan for a pack model
- **Given** a pack model whose Hub files fit a 16 GB card budget,
- **When**  `plan_download` resolves the gguf/pack format,
- **Then**  the result is the whole-set pack directory plan (`dir`, summed `size`),
- **And**   never a single-file gguf pick.
- **Test:** `tests/test_pack_format.py::test_plan_download_returns_a_pack_plan_for_a_pack_model`

### Requirement: card/VRAM gating sizes a pack by the whole file set
The card gate SHALL size a pack-format checkpoint by its WHOLE file set
(`pack_weight_gb`, the summed per-file weight when the format entry states it), never by a
single file, so `fits`/`card_evidence`/`stated_budget_gb` admit or refuse a pack as a set.
A non-pack model keeps its existing single-file budget path.

#### Scenario: the card gate reads a pack's whole-file-set weight
- **Given** a pack whose format entry states per-file weights summing to 9 GB,
- **When**  the pack weight is computed,
- **Then**  it is the whole-file-set sum (never one file's size).
- **Test:** `tests/test_pack_format.py::test_pack_weight_gb_is_the_whole_file_set`

#### Scenario: stated_budget_gb prefers the pack set for the gate
- **Given** a pack and a plain single-file model,
- **When**  each model's stated budget is read,
- **Then**  the pack is sized by its whole set and the single file by its own `weight_gb`.
- **Test:** `tests/test_pack_format.py::test_stated_budget_uses_the_pack_set_for_the_card_gate`

### Requirement: the launch contract wires a pack directory's named parts into one engine config
The launch contract SHALL resolve `MODEL=` to a pack DIRECTORY and SHALL write
`<model_dir>/llgenie-pack-config.json` wiring the engine's declared named parts (per its
params `pack` layout, e.g. `model`, `ple`, `profile`, `labels`, `mtp`) to their absolute
paths under the pack dir, so the engine's launch reads ONE file. `download()` SHALL write
this config when the plan is a pack. An absolute-path part SHALL be passed through
untouched. (A failed config write must never fail the download itself.)

#### Scenario: named parts are written to one engine config file
- **Given** a pack directory on disk and a declared named-part layout,
- **When**  `write_pack_config(model_dir, layout)` runs,
- **Then**  every named part is wired to its absolute path under the pack dir in ONE file,
- **And**   the file carries the model_dir and the layout.
- **Test:** `tests/test_pack_format.py::test_write_pack_config_wires_named_parts_into_one_engine_config`
