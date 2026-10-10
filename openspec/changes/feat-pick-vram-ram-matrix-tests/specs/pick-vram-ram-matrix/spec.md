## ADDED Requirements

### Requirement: every runnable model×engine permutation maps to a concrete fit that yields HF URLs

`matrix(registry, gb, ram_gb, arch)` MUST return the exhaustive set of runnable
(model × engine × plan) permutations: every README trend-list model whose
`vram_tier` fits the VRAM `gb`, every engine with a runnable image variant for
`arch` (cpu fallback; native metal) that reads the model's format, and the
**largest** quantized download whose `plan.size` fits `weight_budget_gb(gb,
is_moe, ram_gb, arch)`. Each row MUST carry `{model, engine, use_format, plan,
url, size_gb}` where `url` is the resolvable
`https://huggingface.co/<repo>/resolve/<rev>/<file>` for every planned file.
Models with no runnable engine or no fitting quant are returned with `why`.

WHEN the matrix is computed for a (vram, ram, arch) key
THEN every permutation has an engine, a plan, and a resolvable HF URL, and the
plan is the largest quant that fits its budget.

#### Scenario: concrete HF URL for a representative vram/ram key
- **Given** a registry with qwen3.8-27b (MoE) and a stubbed Hub tree
- **When** the matrix is computed for a 24 GB cuda host with 32 GB RAM
- **Then** the top row's `url` is the exact resolvable GGUF link of the largest
  quant that fits the MoE budget, and `plan.size` is the largest fitting size
- **Test:** `tests/test_pick_matrix.py::test_matrix_top_row_url_fits_vram_and_ram`

#### Scenario: no row when the vram tier exceeds the card
- **Given** a model whose `vram_tier` exceeds `gb`
- **When** the matrix is computed for that `gb`
- **Then** the model is not present in any permutation
- **Test:** `tests/test_pick_matrix.py::test_matrix_excludes_models_over_vram`

#### Scenario: a moe model binds ram on a tight-ram gpu host
- **Given** a MoE model and a fixed VRAM but shrinking `ram_gb`
- **When** the matrix is computed at each `ram_gb`
- **Then** reducing RAM drops the largest quants (the ones whose size exceeds
  VRAM + (RAM − 4)) and shrinks the per-(model,engine) URL
- **Test:** `tests/test_pick_matrix.py::test_matrix_binds_moe_quant_to_ram`

### Requirement: own-checkpoint engines get only their own plans

`matrix` MUST give a Strata or TensorFold engine its own download (Strata's
`setup.py` shards at its pinned revision; TensorFold's own MLX checkpoints at its
pinned revision), never a generic GGUF of the model's format.

WHEN a Strata/TensorFold engine runs a model in the matrix
THEN its `plan` and `url` are that engine's own files.

#### Scenario: strata gets its own sharded plan
- **Given** a model Strata serves and a matrix call selecting Strata
- **When** the matrix builds Strata's row
- **Then** `url` points at Strata's own shard(s) in its pinned repo/revision
- **Test:** `tests/test_pick_matrix.py::test_matrix_engine_specific_plan_strata`

### Requirement: the matrix scales with vram

Increasing `gb` MUST offer strictly more models (README order kept) and, per
(model, engine), a quant URL whose size is larger or equal, never smaller; a card
too small for even the smallest trend model MUST return an empty matrix.

WHEN VRAM is raised
THEN more models and larger quants become available.

#### Scenario: 16 GB vs 48 GB offer more
- **Given** a registry with models spanning small and large `vram_tier`
- **When** the matrix is computed for 16 GB and 48 GB
- **Then** the 48 GB key returns a superset of the 16 GB permutations, larger
  per-(model,engine) sizes, and a sub-card key returns none
- **Test:** `tests/test_pick_matrix.py::test_matrix_scales_with_vram`

### Requirement: llgenie prints the matrix with HF URLs

`llgenie --matrix [GB] [RAM_GB]` MUST print every permutation (model, engine,
format, size, and each planned HF URL) and exit 0 on stdin not a tty, doing no
download and no serve.

WHEN `llgenie --matrix 24 32` runs non-interactively
THEN it prints the rows with their HF URLs and exits 0.

#### Scenario: --matrix prints rows and exits 0
- **Given** the fixture registry and a stubbed Hub tree on a 24 GB / 32 GB host
- **When** `llgenie --matrix 24 32` runs (stdin not a tty)
- **Then** it exits 0 and prints each permutation's model, engine, size and URL
- **Test:** `tests/test_pick_matrix.py::test_llgenie_matrix_prints_urls`

### Requirement: architecture drives the offered inference servers

The choice of inference server MUST be selected based on the host architecture
(`arch` = cuda / rocm / vulkan / metal / cpu). `matrix` MUST only offer an
engine when that host has a runnable image variant for it: the arch variant
when the engine ships one, else the `cpu` fallback image; on a `metal` host an
engine MUST never fall back to a `cpu` image (issue #120, macOS runs natively).
A cuda-only engine (e.g. TensorRT-LLM) is never offered on rocm/vulkan/cpu/metal.

WHEN the matrix runs for a host of a given architecture
THEN every offered engine uses a real image variant of that architecture, a
Vulkan/CPU-absent engine is dropped or cpu-fallbacked per its variant list, and
a Metal host offers only `metal` variants.

#### Scenario: arch x vram x ram exhaustive permutation set
- **Given** a registry with a cuda-only engine (TensorRT-LLM), a Vulkan-absent
  engine (SGLang) and a Metal-native engine (MLX), and a stubbed Hub tree
- **When** the matrix is computed for every (arch, VRAM, RAM) key of the
  `cuda|rocm|vulkan|cpu|metal` x {8,16,32,64} x {16,32,64} grid
- **Then** every runnable cell carries the largest fitting quant as a resolvable
  `https://huggingface.co/<repo>/resolve/<rev>/<file>` URL, and TensorRT-LLM
  appears only on cuda, SGLang only on cuda/rocm, and MLX only on metal
- **Test:** `tests/test_pick_matrix_arch_perms.py::test_exhaustive_perms_all_map_to_fitting_hf_urls`

#### Scenario: cuda-only engine is never offered off-cuda
- **Given** a model served only by the cuda-only TensorRT-LLM engine
- **When** the matrix runs on rocm / vulkan / cpu / metal
- **Then** the model is returned as skipped-with-reason, never offered
- **Test:** `tests/test_pick_matrix_arch_perms.py::test_arch_drives_engine_selection`

#### Scenario: a metal host never falls back to a cpu image
- **Given** a Metal host with a model served by container engines and MLX
- **When** the matrix runs on the metal architecture
- **Then** only the `metal` variant (MLX) is offered, never a cpu image
- **Test:** `tests/test_pick_matrix_arch_perms.py::test_metal_never_offers_cpu_image`

#### Scenario: --matrix overrides the architecture
- **Given** `llgenie --matrix [--vram V] [--ram R] [--arch A]`
- **When** it runs with a chosen architecture (cuda / metal / cpu) or explicit flags on stdin not a tty
- **Then** it prints that architecture in the header, lists a fitting quant URL, exits 0
- **Test:** `tests/test_pick_matrix_arch_perms.py::test_llgenie_matrix_arch_override_in_header`,
  `::test_llgenie_matrix_explicit_flags`, `::test_llgenie_matrix_flag_wins_over_positional`

### Requirement: the real trending registry is asserted exhaustively

`matrix` MUST be run against the REAL vendored registry (data/models.json) — every
trending model, every engine the registry says can serve it, on every
(arch, vram, ram) key — not a synthetic fixture. Per permutation the test asserts an
engine is offered iff its format has a quant within the weight budget AND it has a
runnable image for the arch; the chosen download is the largest-quant-that-fits; and
the expected quantized HF download llgenie would use before starting the engine is a
resolvable `https://huggingface.co/<repo>/resolve/<rev>/<file>` URL.

WHEN the matrix is computed for every (model x engine x arch x vram x ram)
THEN every offered engine has a concrete, resolvable HF quant URL (largest that
fits) and neither silently-offered-no-engine nor silently-absent models occur.

#### Scenario: every real model x engine permutation resolves to a concrete HF URL
- **Given** the real data/models.json and the generated engine params
- **When** the matrix is computed for every (model, engine, arch, vram, ram) permutation
- **Then** an engine is offered iff it fits the arch AND a quant fits the budget, and
  every offered cell's `url` is a resolvable HF quant link
- **Test:** `tests/test_pick_full_registry.py::test_pick_matrix_any_offer_is_a_real_fitting_hf_url`
  (1260 permutations over the real registry, LIVE)

#### Scenario: the expected HF quant file exists (HTTP 200) on the Hub
- **Given** a real trending model from data/models.json
- **When** llgenie's own download plan is computed (hermetic — from the committed HF
  class table) and its links are probed on the live Hub
- **Then** every expected quantized download URL answers HTTP 200/206 on a ranged GET
- **Test:** `tests/test_pick_full_registry.py::test_pick_matrix_real_quant_links_exist`

### Requirement: the use cases run through the REAL llgenie CLI (engine start mocked)

`matrix` MUST be exercised at the use-case level, not only as a function: the CI runs
the actual `llgenie` launcher (scripts/llama_serve.py) via
`llgenie --pick <model> --engine <engine> --dry` for every real (model, engine, arch)
the registry + engine set implies, with the inference server start mocked by `--dry`
(it returns before the start script's `os.execv`). The CLI and the business logic must
AGREE: where `matrix()` offers an engine, the CLI must resolve to an engine on that
architecture's image variant, plan a real HF download, and print the start-script
command; where it does not, the CLI must refuse cleanly — never starting an engine.

WHEN `llgenie --pick <model> --engine <engine> --dry` runs for every registered
(model x engine x arch)
THEN the CLI agrees with `matrix()` (offered => engine + variant + download + start
script before any engine starts; not-offered => clean refusal).

#### Scenario: the real CLI pick agrees with matrix per model x engine x arch
- **Given** the real data/models.json, the generated engine params, and the live Hub
- **When** `llgenie --pick <model> --engine <engine> --dry` runs for every
  (model, engine, arch) on a 24 GB / 64 GB host
- **Then** every offered pair resolves to that engine on the arch's image variant with a
  real HF download and the start-script command (engine start mocked by --dry), and
  every not-offered pair is refused cleanly
- **Test:** `tests/test_pick_full_registry.py::test_pick_matrix_llgenie_cli_agrees_with_business_logic`
  (every real model x engine x arch), `::test_pick_matrix_engine_supported_quants_catalog`

### Requirement: the per-engine supported-quant range is first-class business logic

`engine_supported_quants(model, engine, gb, ram_gb, arch)` MUST return the real range of
quantized models a chosen engine supports for a model on the (env-stubbed) host, in
ascending size — only quants of a format that engine reads (own-checkpoint engines
Strata/TensorFold return only their own files), each a resolvable download plan within
the budget. `pick_quant` MUST return the last (highest) of them — the interactive pick's
download once the engine is chosen. `matrix` MUST use the same path (`pick_quant`) for
every cell, so the matrix, the per-engine range, the highest-quant pick and the CLI all
share one code path.

WHEN the user has picked a model and selected an engine on a (vram, ram, arch) host
THEN the engine offers only its own format's quants that fit the budget, each a real
resolvable HF link, and the highest one is the interactive pick's download.

#### Scenario: the supported-quant range is ascending, budget-fitting and engine-specific
- **Given** a real model and its engines on a 24 GB / 64 GB cuda host (env-stubbed)
- **When** `engine_supported_quants` is called for a gguf engine and an mlx engine
- **Then** each range is ascending and budget-fitting, the gguf engine only lists gguf
  files and the mlx engine only whole-repo MLX snapshots, and `pick_quant` returns the
  highest element
- **Test:** `tests/test_engine_supported_quants.py::test_supported_quants_are_ascending_and_fit_budget`,
  `::test_supported_quants_narrow_to_the_engines_own_format`

#### Scenario: every supported quant is a real catalog link
- **Given** a real (model x engine x arch) and the committed trending-quant catalog
- **When** the engine's supported quant range is computed (hermetic — from the committed
  table, no live Hub re-query in the pick path)
- **Then** every supported quant's URL is a real link in the catalog and answers HTTP 200
- **Test:** `tests/test_engine_supported_quants.py::test_every_supported_quant_is_a_real_catalog_link`,
  `::test_pick_is_a_real_catalog_link`

### Requirement: a committed catalog of the trending models' real quant links

`data/trending-quant-catalog.json` (generated by scripts/
gen_trending_quant_catalog.py from data/models.json + the live Hub, read-only — it never
downloads) MUST be the HF class table llgenie's pick logic resolves against: for every
trending model and each engine that can run it, the archs that engine supports (`arch`, a
subset of its real image variants) and the real quantized download plans with their
downloadable `https://huggingface.co/<repo>/resolve/<rev>/<file>` links
(`{model: {engine: {arch, quants}}}`). Deciding what a chosen engine can load on this
hardware is **hermetic** — it reads this committed table and never re-queries the live Hub
in the comparison path (the Hub is touched only when actually downloading). A (model,
engine) not yet in the table falls back to live resolution. The committed test fixture
`tests/fixtures/trending-quant-catalog.json` MUST exactly match the canonical `data/`
table, so a link change or a dropped section is a caught regression. Both the unit catalog
test and the system pick-matrix test assert against it.

WHEN the catalog is read
THEN it is well-formed, every model/engine is real, every engine's `arch` is a subset of
its real image variants, every URL is a concrete resolvable download link that exists
(HTTP 200) — no fabricated links — and the fixture exactly matches the canonical table.

#### Scenario: the fixture matches the canonical catalog (regression guard)
- **Given** data/trending-quant-catalog.json and tests/fixtures/trending-quant-catalog.json
- **When** they are compared byte-for-byte
- **Then** they are identical — a link change or a dropped section of the table is a
  caught regression and must be reviewed and committed by `make sync-quant-catalog`
- **Test:** `tests/test_trending_quant_catalog.py::test_fixture_exactly_matches_the_canonical_catalog`

#### Scenario: the quant catalog is well-formed and points at real files
- **Given** data/trending-quant-catalog.json
- **When** it is validated and a bounded sample probed
- **Then** it is well-formed (`{model: {engine: {arch, quants}}}`), every
  model/engine/URL is real, each engine's `arch` ⊆ its image variants, and the sample
  answers HTTP 200
- **Test:** `tests/test_trending_quant_catalog.py::test_catalog_is_well_formed`,
  `::test_every_model_and_engine_is_real`, `::test_bounded_sample_of_real_links_exist_http_200`

#### Scenario: an engine llgenie offers on an arch is catalogued on that arch
- **Given** a real registry model and an engine `rank_engines` offers on this host
- **When** the catalog cell for (model, engine) is looked up
- **Then** it exists and lists the offered arch — llgenie can only offer the engines the
  table's `arch` list allows for that model on that hardware
- **Test:** `tests/test_trending_quant_catalog.py::test_every_engine_and_arch_that_llgenie_offers_is_catalogued`

#### Scenario: the generator validates the NEW links vs the prior table (all on first run)
- **Given** a prior generated table, a refreshed link set, and the generator's sync
  decision (`links_to_validate`)
- **When** the sync runs on a first generation, on a refresh, or after links change
- **Then** a first run validates ALL links; a refresh probes ONLY the newly-added links;
  a refresh that only drops links probes nothing newly-added; dead new links FAIL the
  sync without writing the table; `--check` fails when the committed table differs from
  what the generator produces — the catalog is sensitive to every change
- **Test:** `tests/test_quant_generator_edges.py::test_first_run_probes_every_link`,
  `::test_update_probes_only_new_links`, `::test_update_with_only_a_removed_link_probes_nothing`,
  `::test_check_fails_when_generated_differs_from_committed`,
  `::test_check_passes_when_committed_matches_generated`,
  `::test_sync_fails_when_a_new_link_is_dead`, `::test_sync_writes_canonical_and_fixture_together`

### Requirement: Linux auto-provisions Python 3.11 via uv (make install works out of the box)

`scripts/check_python.py` MUST resolve a Python 3.11 for the gguf venv on Linux the same
way it already does on macOS: when the running interpreter is not 3.11, it looks for
`python3.11` on PATH, then a uv-managed 3.11 (even when not on PATH), then brew (macOS).
When none exists and `uv` is on PATH, it MUST run `uv python install 3.11` as part of
`make -C tools create-venv` (the Linux analogue of the macOS brew path), so `make install`
works on a host that ships only a newer Python (e.g. Omarchy's 3.14). A host with neither
uv nor 3.11 still fails closed with an actionable message.

WHEN `make -C tools create-venv` runs on a Linux host with uv but no python3.11
THEN it provisions 3.11 via `uv python install 3.11` and builds the venv; a uv-managed
3.11 is found even when not on PATH; a host with neither uv nor 3.11 exits 1 with a
message naming the uv route.

#### Scenario: a uv-managed python3.11 is found even when not on PATH
- **Given** a uv-managed python3.11 that is not on PATH
- **When** `find_python311` runs
- **Then** it resolves the uv-managed interpreter (PATH and brew are not required)
- **Test:** `tests/test_check_python_uv.py::test_finds_uv_managed_python311_not_on_path`

#### Scenario: uv auto-provisions 3.11 when it is missing
- **Given** a Linux host with uv on PATH but no python3.11 anywhere
- **When** `resolve` runs
- **Then** it runs `uv python install 3.11` and returns the now-managed interpreter
- **Test:** `tests/test_check_python_uv.py::test_auto_provisions_via_uv_when_missing`

#### Scenario: a host with neither uv nor 3.11 fails closed
- **Given** a host with neither uv nor any python3.11
- **When** `resolve` / `real_main` run
- **Then** it does not provision, returns None / exits 1, and the message names the uv route
- **Test:** `tests/test_check_python_uv.py::test_fails_closed_with_no_uv_and_no_311`,
  `::test_real_main_fails_closed_with_actionable_message`
