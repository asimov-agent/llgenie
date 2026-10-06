## ADDED Requirements

### Requirement: the registry is vendored and synced by make
llgenie MUST read `data/models.json` (a verbatim copy of the trending-local-llms registry)
unless `LLGENIE_REGISTRY_SRC` is set, and MUST NOT fetch the registry at run time.
`make sync-registry` MUST replace it with the validated upstream file, and
`make check-registry` MUST fail on an invalid vendored file.

WHEN llgenie ranks models without `LLGENIE_REGISTRY_SRC`
THEN it reads `data/models.json`.

#### Scenario: default registry is the vendored file
- **Given** no `LLGENIE_REGISTRY_SRC`
- **When** the registry is loaded
- **Then** it equals `data/models.json` and passes validation
- **Test:** `tests/test_trend_pick.py::test_default_registry_is_the_vendored_file`

#### Scenario: sync validates and writes only on change
- **Given** a valid source file and an invalid one
- **When** `scripts/sync_registry.py` syncs each into a temp target
- **Then** the valid one is written verbatim (a second sync reports unchanged) and the invalid one exits non-zero without writing
- **Test:** `tests/test_trend_pick.py::test_sync_writes_valid_registry_and_rejects_invalid`

#### Scenario: a README copy passes, a modified copy is rejected
- **Given** the vendored registry and copies of its README
- **When** the match is checked against a byte-for-byte copy, a copy with two rows swapped, a copy with a row removed, and a copy whose best CUDA engine was renamed
- **Then** the good copy is accepted and synced, and each modified copy is rejected naming the change, without writing the registry
- **Test:** `tests/test_trend_pick.py::test_readme_copy_passes_and_a_modified_copy_is_rejected`

#### Scenario: vendored file is in sync with upstream (live)
- **Given** the live upstream registry
- **When** `make sync-registry` runs in the registry-sync workflow
- **Then** a changed file opens a PR from `chore/registry-sync`
- **Test:** `.github/workflows/registry-sync.yml` (workflow_dispatch)

### Requirement: llgenie with no model shows the README trend list that fits the card
With no model argument, llgenie MUST list exactly the upstream README "Most loved" models
whose README VRAM column fits the card's nominal size, in README order. Rows that cannot be
served here (no engine image for this backend, no GGUF reader, no GGUF that fits) MUST stay
in the list, unnumbered, with the reason. The chosen model's engines MUST rank figures
measured on this host's kind of hardware first, highest t/s first. `--auto` or a
non-terminal stdin MUST take the first servable model and its top engine.

WHEN `llgenie` runs with no model on a terminal
THEN it prints the README list that fits, asks for a numbered model, then for an engine.

#### Scenario: the list is the README list that fits the card
- **Given** the vendored `data/models.json` + `data/trending-README.md`
- **When** the list is built for cuda/16, cuda/24, cpu/16, rocm/8, vulkan/48 and cpu/2
- **Then** its names are the README "Most loved" names whose VRAM <= the card, in README order
- **Test:** `tests/test_trend_pick.py::test_llgenie_list_is_the_readme_list_that_fits_the_card`

#### Scenario: 16 GB cuda card (nvidia-smi 15.99 GiB), 64 GB RAM
- **Given** a 15.99 GiB cuda card and 64 GB system RAM
- **When** the list is built
- **Then** all 11 README models with VRAM <= 16 GB are listed in README order and every one is selectable: the 125B MoE on Strata (its top engine, 124 t/s on an RTX 4090) as GGUF, RavenX as MLX safetensors, Gemma 4 E2B as LiteRT; 18/24/48 GB models are absent
- **Test:** `tests/test_trend_pick.py::test_card_16gb_list_on_this_readme`, `::test_every_readme_model_maps_to_its_best_engine`

#### Scenario: mapping registry engine -> skill -> image variant -> format -> download
- **Given** every engine name in the registry and the generated engine params
- **When** they are mapped for cuda/rocm/vulkan/cpu hosts
- **Then** each name maps to its skill's id or to no image (a drafter, a benchmark harness, or a browser library); Strata, being an OpenAI server, maps to its own cuda and rocm images; the variant is the host backend, else cpu, never a disabled #103 one; hardware strings map to CUDA/ROCm/CPU/Metal as upstream; engines rank same-hardware, then other-hardware, then supported-only; each format has a live-Hub download plan within the budget
- **Test:** `tests/test_trend_pick.py::test_every_registry_engine_name_maps_to_its_skill_or_has_no_image`, `::test_engine_maps_to_the_host_variant_with_cpu_fallback`, `::test_measurement_hardware_maps_to_a_backend`, `::test_engine_order_same_hw_then_other_hw_then_supported_only`, `::test_plan_download_per_format_live_hub`, `::test_weight_budget_rules`, `::test_moe_model_on_16gb_is_planned_with_system_ram`

#### Scenario: select any row without a terminal, download it if missing
- **Given** an empty models dir
- **When** `llgenie --select N --dry` runs for every row of the 16 GB list, and `llgenie --select 1` (no --dry) on a 2 GB cpu card
- **Then** each row plans its download and that row's top engine's start script; the real run downloads the complete GGUF (size == Hub size) and a second run reuses it
- **Test:** `tests/test_trend_pick.py::test_select_every_row_plans_a_download_and_the_right_engine`, `::test_select_downloads_a_missing_model_for_real`, `::test_trend_flag_prints_the_numbered_readme_list`, `::test_download_mlx_repo_snapshot_for_real`

#### Scenario: engine t/s from this host's hardware
- **Given** Qwen3.8-27B with llama.cpp figures on an RTX 5090 Laptop and on AMD
- **When** its engines are ranked for cuda and for rocm
- **Then** cuda uses the RTX figure and ranks the AMD-only fork last; rocm ranks an AMD figure first
- **Test:** `tests/test_trend_pick.py::test_engine_tps_comes_from_the_hosts_hardware_first`

#### Scenario: interactive pick in a pty
- **Given** the vendored registry, an empty models dir, a 16 GB cpu host
- **When** `llgenie --dry` runs in a pty and the user answers 1 then 1 (and invalid answers are re-prompted)
- **Then** every printed row is a README model in README order, unservable rows are marked, and pick 1 is the first servable model with its top engine and a Hub GGUF
- **Test:** `tests/test_trend_pick.py::test_llgenie_no_args_is_the_interactive_trend_pick`, `::test_model_pick_reprompts_on_invalid_input`

### Requirement: the vendored registry is the README list
`make sync-registry` MUST vendor upstream `data/models.json` and `README.md` and reject a
registry whose model order is not the README "Most loved" order; `make check-registry` MUST
check the same on the vendored files.

#### Scenario: order mismatch is rejected
- **Given** the registry with two models swapped
- **When** it is synced against the README
- **Then** the sync exits 1 and writes nothing
- **Test:** `tests/test_trend_pick.py::test_sync_rejects_a_registry_whose_order_is_not_the_readme`, `::test_live_upstream_registry_is_the_live_readme_list`, `::test_bands_match_the_readme_status_column`

### Requirement: the downloaded GGUF fits the card
llgenie MUST download the largest loadable GGUF model (split shards summed, never MTP heads,
imatrix or mmproj) within 80% of the card minus 1 GiB, plus 70% of system RAM for MoE models.

#### Scenario: budget and MoE
- **Given** a 16 GB card
- **When** the budgets and Qwen3.8-Flash-Next 125B are planned with 8 GB and 256 GB RAM
- **Then** dense = 11.8 GB; the MoE model does not fit with 8 GB RAM and plans all shards with 256 GB
- **Test:** `tests/test_trend_pick.py::test_moe_budget_uses_system_ram_and_unfit_models_say_why`, `::test_unsloth_repo_skips_mtp_heads_and_imatrix`

### Requirement: a GGUF repo is resolved for every recommended model
llgenie MUST download from the registry repo when it holds `.gguf` files, else from the
most-downloaded Hub repo named `<name>-GGUF` (same org first).

WHEN a recommended model's registry repo has no `.gguf`
THEN a `*-GGUF` repo with `.gguf` files is used.

#### Scenario: every vendored recommendation resolves (live Hub)
- **Given** the vendored registry and the live Hub API
- **When** `gguf_repo()` runs for every model `recommend()` offers on a 48 GB card
- **Then** each returns a repo whose tree lists at least one `.gguf`
- **Test:** `tests/test_trend_pick.py::test_every_recommended_model_resolves_to_a_hub_gguf_repo`

### Requirement: manual model + engine pairs are checked for compatibility
`llgenie --engines [model]` MUST list the engines with an enabled image for this host (all,
or those compatible with the model). A manual `--engine` MUST be compatible with the model
(image variant for this host and the skill `formats` include the model format) or llgenie
MUST exit non-zero naming the compatible engines.

WHEN an incompatible pair is given
THEN llgenie exits non-zero and lists the compatible engines.

#### Scenario: list engines and reject an incompatible pair
- **Given** a local `.gguf` on a cpu host
- **When** `llgenie --engines` and `llgenie <file> --engine litert --dry` run
- **Then** the first lists llama.cpp and ollama, the second exits non-zero naming compatible engines; `--engine ollama --dry` uses `llgenie-engine-ollama` with that file
- **Test:** `tests/test_trend_pick.py::test_engines_listing_and_manual_pair_compatibility`

### Requirement: make install is verified with the trend flow
After `make install`, CI MUST run the installed `~/bin/llgenie` through the trend flow.

#### Scenario: install job serves a real trend pick
- **Given** `make install` in the test container on a mocked 2 GB cpu card
- **When** `~/bin/llgenie` runs with no model in a pty, the user picks 1 and 1
- **Then** the model list comes from `data/models.json`, the GGUF is downloaded from the Hub, and the engine container answers "hi"
- **Test:** `tests/test_install_trend.py::test_installed_llgenie_trend_pick_downloads_and_answers` (`make test-install-trend`, inside `make test-install-ci`)

#### Scenario: install-published runs the trend flow per backend
- **Given** `make install ARCH=<backend>` from the published images on a mocked 2 GB card
- **When** `~/bin/llgenie` runs with no model in a pty with answers 1 and 1
- **Then** the list and the engines come from `data/models.json` for that backend, the full GGUF is downloaded (size == Hub size) and that backend's engine image answers "hi"
- **Test:** `tests/test_install_published.py::test_make_install_pulls_this_backends_published_images_and_they_answer` (`make test-install-published BACKEND=<backend>`)

### Requirement: a stalled hf-xet download falls back to plain HTTP
`scripts/hf_download.py` MUST retry a download that stalled with `HF_HUB_DISABLE_XET=1`.

WHEN a download makes no progress under hf-xet
THEN the retry runs over plain HTTP and completes.

#### Scenario: xet stall -> HTTP
- **Given** an `hf` that never progresses with xet but works over HTTP
- **When** `hf_download.py` runs with a 4 s stall threshold
- **Then** attempt 1 stalls, attempt 2 runs with `HF_HUB_DISABLE_XET=1` and exits 0
- **Test:** `tests/test_hf_download_stall.py::test_xet_stall_falls_back_to_plain_http`

### Requirement: the download logic works against the real Hub
`download()` MUST place the complete GGUF, `pick_file()` MUST take the largest file
leaving 15% of the card free (smallest if none fit) and skip shards and mmproj.

#### Scenario: full real download
- **Given** `aladar/tiny-random-LlamaForCausalLM-GGUF` and no byte cap
- **When** it is downloaded for a 2 GB card
- **Then** the file size equals the Hub size, starts with `GGUF`, and `resolve_local` finds it
- **Test:** `tests/test_trend_pick.py::test_full_download_through_hf_download_places_the_complete_gguf`

### Requirement: the published-image digest check survives a transient registry error
`engine_image._digest` MUST retry a failed manifest lookup before reporting a missing tag.

WHEN a GHCR manifest lookup fails once
THEN it is retried and the real digest is compared.

#### Scenario: live digest lookup
- **Given** the published llama.cpp cpu image on GHCR
- **When** its pinned tag and `:cpu` are looked up, and a non-existent tag with 2 attempts
- **Then** both digests are the same `sha256:`, the missing tag is retried and returns ""
- **Test:** `tests/test_engine_skills.py::test_digest_reads_the_live_registry_and_retries_a_failed_lookup`
