## ADDED Requirements

### Requirement: Strata downloads exactly the files its setup.py names
When the chosen inference server is Strata, llgenie MUST plan and download every shard of the
choice Strata's own `setup.py --yes` installs on this host (family, size, repo, pinned revision
and file names from `data/strata_models.json`), and MUST NOT plan any other GGUF for Strata.

#### Scenario: the vendored map is Strata's setup.py at the pinned commit
- **Given** Strata's source at the skill's pinned commit
- **When** `make check-strata-models` runs, and again against a drifted copy
- **Then** the vendored map passes and the drifted copy fails; the map's families, sizes and revisions equal setup.py's tables in setup's order
- **Test:** `tests/test_strata_download.py::test_vendored_map_matches_strata_setup_py_at_the_pinned_commit`, `::test_map_tables_equal_setup_py_tables`, `::test_map_pinned_commit_is_the_image_commit`

#### Scenario: the choice is setup.py's default for the RAM
- **Given** 8, 32, 48, 59, 60, 64 and 128 GB of RAM
- **When** the Strata choice is computed
- **Then** it is `qwen` `Q2_0` below 60 GB and `qwen` `IQ3_XXS` from 60 GB
- **Test:** `tests/test_strata_download.py::test_choice_is_setup_py_default_for_the_ram`

#### Scenario: every planned file name is what setup.py builds and maps back
- **Given** every (family, size) setup.py offers
- **When** llgenie names the shards
- **Then** they equal `setup.model_file` for `setup.model_shards` shards, `setup.gguf_choice(first shard)` is the same choice, and `setup.gguf_dir_shards` / `gguf_dir_problem` accept the downloaded folder
- **Test:** `tests/test_strata_download.py::test_every_choice_file_name_is_what_setup_py_builds_and_maps_back`, `::test_downloaded_folder_is_accepted_by_setup_py_gguf_dir`

#### Scenario: the plan is every shard at the pinned revision (live Hub), never UD-IQ1_M
- **Given** the 125B model on a 16 GB cuda card with 48 or 64 GB of RAM
- **When** the Strata plan is made
- **Then** it is both shards of the choice from `ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF` at setup.py's revision, sized from the Hub; Unsloth's UD-IQ1_M is refused by setup.py and never planned; other models and formats get no Strata plan, and llama.cpp keeps its own plan
- **Test:** `tests/test_strata_download.py::test_plan_is_every_shard_from_strata_repo_at_its_pinned_revision_live_hub`, `::test_the_old_unsloth_ud_iq1_m_is_refused_by_strata_and_never_planned`, `::test_strata_plan_ignores_other_engines_and_formats`, `::test_offer_gives_strata_its_own_plan_and_llama_cpp_its_own`

#### Scenario: the hf downloader fetches every shard at the pinned revision
- **Given** the Strata plan
- **When** it is downloaded (first bytes of every shard; a full small file through `scripts/hf_download.py` with `HF_REVISION`)
- **Then** every shard starts with the GGUF magic and `hf download --revision <sha>` placed the file
- **Test:** `tests/test_strata_download.py::test_download_fetches_the_first_bytes_of_every_shard_at_the_pinned_revision`, `::test_hf_downloader_uses_the_pinned_revision_for_real`, `::test_download_passes_the_revision_to_the_hf_downloader`

#### Scenario: a complete local set is reused, a partial or unsupported one is not
- **Given** a partial IQ3_XXS set, Unsloth's UD-IQ1_M set, then a complete Q2_0 set, then a complete IQ3_XXS set
- **When** the Strata local copy is resolved
- **Then** nothing, then Q2_0, then this host's own choice; with a local copy there is no download
- **Test:** `tests/test_strata_download.py::test_complete_local_set_is_reused_partial_and_unsupported_are_not`

### Requirement: Strata starts on the downloaded choice
Strata's `pre_launch` MUST pass setup `--family F --model M` from Strata's own
`gguf_choice(<first shard>)` next to `--gguf-dir`, and MUST stop with an error for a file
Strata cannot run.

#### Scenario: pre_launch names the choice, refuses other files
- **Given** the image's `pre_launch` run with Strata's real setup.py on a downloaded shard set, and on UD-IQ1_M
- **When** it computes setup's arguments
- **Then** `--gguf-dir` is the shard folder and `--family`/`--model` are the planned choice; UD-IQ1_M exits non-zero naming it
- **Test:** `tests/test_strata_download.py::test_pre_launch_names_the_downloaded_choice`, `::test_pre_launch_refuses_a_file_strata_cannot_run`

### Requirement: interactive llgenie downloads the chosen engine's files
The interactive pick MUST download (and `--dry` MUST print) the plan of the inference server the
user chose, and start that server on the first planned file.

#### Scenario: pick 1 then Strata, pick 1 then llama.cpp, a local Strata set
- **Given** interactive `llgenie --dry` in a pty on a 16 GB cuda host
- **When** the user picks 1 (the 125B) and then Strata (48 and 64 GB RAM), llama.cpp, or Strata with a complete local set
- **Then** Strata: both shards of Strata's choice are listed and `llgenie-engine-strata` gets the first shard; llama.cpp: its own Unsloth plan; local set: `[local]`, no download
- **Test:** `tests/test_strata_download.py::test_interactive_pick_strata_downloads_strata_files_and_starts_strata_on_them`, `::test_interactive_pick_llama_cpp_for_the_same_model_gets_its_own_files`, `::test_interactive_reuses_a_complete_local_strata_set`
