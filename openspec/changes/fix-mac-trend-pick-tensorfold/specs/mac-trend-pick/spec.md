## ADDED Requirements

### Requirement: an Apple-Silicon Mac is a metal host with native Metal engines
`model_engine_pick.host_arch()` MUST return `metal` when detect_server reports Metal.
Every servable engine skill with `metal` in its backends and a metal install MUST be
offered on a metal host with the native variant `metal`. Container-only engines MUST
fall back to their cpu image, and cuda/rocm-only engines MUST NOT be offered. No Linux
backend MAY ever be offered a `metal` variant.

WHEN llgenie runs on an Apple-Silicon Mac
THEN the list header names `metal` and TensorFold / MLX / llama.cpp are offered natively.

#### Scenario: the host is metal, not cpu
Given  detect_server reports the metal backend,
When   llgenie asks for the host arch,
Then   it is `metal`,
And    Metal measurements count as this host's hardware.
- **Test:** `tests/test_mac_trend_pick.py::test_apple_silicon_host_is_metal_not_cpu`

#### Scenario: the Metal engines come from the skills
Given  every engine skill,
When   the Metal engines are derived,
Then   they are TensorFold, MLX, llama.cpp, Prism, Ollama and LiteRT,
And    the MLX-fast benchmark harness is not one of them.
- **Test:** `tests/test_mac_trend_pick.py::test_metal_engines_are_the_servable_skills_with_a_metal_install`

#### Scenario: a metal host's engines
Given  a metal host,
When   its engines are listed,
Then   the Metal engines have variant `metal`,
And    vLLM falls back to its cpu image,
And    Strata, SGLang, FreeToken, TensorRT-LLM and ExLlamaV3 are absent.
- **Test:** `tests/test_mac_trend_pick.py::test_metal_host_engines_include_tensorfold_native_and_no_cuda_only_engine`

#### Scenario: Linux hosts never get metal
Given  cuda, rocm, vulkan and cpu hosts,
When   their engines are listed,
Then   no engine has the `metal` variant.
- **Test:** `tests/test_mac_trend_pick.py::test_linux_hosts_never_get_a_metal_variant`

#### Scenario: the TensorFold image is CUDA-only and built by Linux CI
Given  the generated TensorFold params and the CI image matrix,
When   the matrix is computed,
Then   TensorFold's only image is `cuda` and CI builds it,
And    on metal TensorFold is a native `uv tool install` of the pinned tag.
- **Test:** `tests/test_mac_trend_pick.py::test_tensorfold_image_is_cuda_only_and_built_by_linux_ci`

### Requirement: the metal memory budget is the GPU working set
On a metal host `weight_budget_gb` MUST be 70% of unified memory minus 7 GiB (floor
40%), and MoE models MUST NOT add system RAM (it is the same memory).

WHEN a model is planned on a Mac
THEN its download must fit 70% − 7 GiB of the unified memory.

#### Scenario: budget per Mac size
Given  a Mac with 8, 16, 48 or 128 GiB,
When   the dense and MoE budgets are computed,
Then   they are 3.2, 6.4, 26.6 and 82.6 GiB, the same for MoE.
- **Test:** `tests/test_mac_trend_pick.py::test_metal_budget_is_the_gpu_working_set_minus_reserves`

### Requirement: TensorFold is offered with its own MLX checkpoints
TensorFold MUST be planned only with its own checkpoints (`TensorFold/<base>-MLX-*`):
the largest that fits the budget, or a local `~/models/TensorFold__<base>-MLX-*` copy.
A row whose engines have nothing that fits MUST name the smallest TensorFold MLX size
and the smallest GGUF size against the budget. An MLX engine MUST also find a model's
`<base>-MLX*` conversions on the Hub.

WHEN the trend list is built on a Mac
THEN TensorFold rows download a TensorFold checkpoint, and a row too large says by how much.

#### Scenario: the reporter's 48 GB Mac list
Given  the vendored README list and a 48 GB Mac,
When   `llgenie --trend` prints it,
Then   the header says `(48 GB, metal)`,
And    every row is printed in README order, numbered only where servable,
And    pick 1 is Qwen3.8-27B on TensorFold [metal] with its 189 t/s M5 Max figure.
- **Test:** `tests/test_mac_trend_pick.py::test_trend_on_a_48gb_mac_is_the_readme_list_with_metal_engines`

#### Scenario: Flash Next does not fit 48 GB
Given  a 48 GB Mac,
When   the Qwen3.8-Flash-Next 125B row is built,
Then   it has no engine,
And    its reason names the smallest TensorFold MLX and smallest GGUF against 27 GB.
- **Test:** `tests/test_mac_trend_pick.py::test_flash_next_on_48gb_says_tensorfold_needs_more_memory`

#### Scenario: Flash Next is pick 1 on TensorFold on a 128 GB Mac
Given  a 128 GB Mac,
When   the list is built,
Then   Qwen3.8-Flash-Next 125B is pick 1 on TensorFold [metal],
And    its plan is a TensorFold MLX checkpoint within the budget.
- **Test:** `tests/test_mac_trend_pick.py::test_flash_next_is_number_one_with_tensorfold_on_a_128gb_mac`

#### Scenario: --select 1 on 48 GB serves Qwen3.8-27B with TensorFold
Given  a 48 GB Mac with no local models,
When   `llgenie --select 1 --dry` runs,
Then   it plans a `TensorFold/Qwen3.8-27B-MLX-*` download and the native TensorFold start script.
- **Test:** `tests/test_mac_trend_pick.py::test_select_1_on_a_48gb_mac_serves_qwen38_27b_with_tensorfold`

#### Scenario: --select with --engine tensorfold on 128 GB
Given  a 128 GB Mac,
When   `llgenie --select 1 --engine tensorfold --dry` runs,
Then   Flash Next is served by TensorFold from a TensorFold checkpoint.
- **Test:** `tests/test_mac_trend_pick.py::test_select_flash_next_with_tensorfold_on_a_128gb_mac`

#### Scenario: an MLX-only model finds its MLX conversion
Given  a 48 GB Mac,
When   the Ornith 1.5 row is built,
Then   it is servable on MLX [metal] with a `-MLX` repo snapshot.
- **Test:** `tests/test_mac_trend_pick.py::test_mlx_only_model_finds_its_mlx_conversion_on_a_mac`

#### Scenario: the interactive listing is the --trend listing
Given  the `--trend` output for a 48 GB Mac,
When   plain `llgenie --dry` reaches its prompt in a terminal,
Then   the listed rows are identical,
And    pick 1 is TensorFold [metal].
- **Test:** `tests/test_mac_trend_pick.py::test_interactive_listing_is_the_trend_listing`

### Requirement: Metal engines run natively from a start script
For a metal engine, llgenie MUST install the engine with its skill when the skill's detect
fails, MUST write `~/bin/llgenie-engine-<id>` serving through `engine_skills.py serve
--backend metal`, and MUST NOT start or repair a container runtime for it.

WHEN a Metal engine is picked
THEN it is installed once natively and served without docker.

#### Scenario: native start script
Given  TensorFold on metal,
When   its start script is rendered,
Then   it serves and detects through the skill with `--backend metal`,
And    it contains no container run,
And    `make uninstall` recognises it.
- **Test:** `tests/test_mac_trend_pick.py::test_native_start_script_runs_the_skill_not_a_container`

#### Scenario: install once, then reuse
Given  TensorFold not installed, then installed,
When   llgenie ensures it twice,
Then   it is installed natively exactly once,
And    its executable native start script is written.
- **Test:** `tests/test_mac_trend_pick.py::test_ensure_on_metal_installs_natively_once_and_writes_the_script`

### Requirement: picking a Metal engine makes it ready whether or not it is installed
Interactive `llgenie` is, by design: hardware → the README trend list that fits → the model
→ its supported engines → the engine. When the picked engine is a native Metal engine
(TensorFold), llgenie MUST make it ready with the skill's own install script, whatever is on
the host: install it when missing, update it when the installed version differs from the
skill's pinned `version:` (older or newer), reuse it when it is at the pin. Then it MUST serve
the model through it, downloading the model's TensorFold checkpoint when it is not local. The
engine list MUST show which of the three will happen. `--dry` MUST NOT install anything. A
failed install MUST fail loudly and leave no start script behind.

WHEN the user picks a model and TensorFold in llgenie on a Mac
THEN TensorFold is installed/updated/reused at the pinned release, the checkpoint is
downloaded if missing, and the model is served on Metal.

#### Scenario: the pinned release comes from the skill
Given  the TensorFold and llama.cpp skills,
When   their pinned release is read,
Then   TensorFold pins its tagged release,
And    a branch-tracking skill pins none.
- **Test:** `tests/test_tensorfold_seamless.py::test_pinned_version_comes_from_the_skill`

#### Scenario: install state is missing, outdated or current
Given  TensorFold absent, at an older release, or at the pinned release,
When   its native state is read through the skill's detect,
Then   it is missing / outdated / current, with the installed and wanted versions.
- **Test:** `tests/test_tensorfold_seamless.py::test_native_status_missing_outdated_current`

#### Scenario: missing TensorFold is installed with its install script
Given  a Mac without TensorFold,
When   llgenie ensures TensorFold for the pick,
Then   the skill's exact install step ran once at the pinned tag,
And    TensorFold is current and its native start script exists.
- **Test:** `tests/test_tensorfold_seamless.py::test_missing_tensorfold_is_installed_with_its_skill_install_script`

#### Scenario: an older TensorFold is updated
Given  TensorFold at an older release,
When   llgenie ensures TensorFold,
Then   it reinstalls the pinned release with the same step.
- **Test:** `tests/test_tensorfold_seamless.py::test_outdated_tensorfold_is_updated_to_the_pinned_release`

#### Scenario: a newer, untested TensorFold goes back to the pin
Given  TensorFold at a newer release than the skill pins,
When   llgenie ensures TensorFold,
Then   it is at the pinned release.
- **Test:** `tests/test_tensorfold_seamless.py::test_newer_unpinned_tensorfold_is_brought_back_to_the_pinned_release`

#### Scenario: a current TensorFold is reused
Given  TensorFold at the pinned release,
When   llgenie ensures it twice,
Then   nothing is installed and the start script is written.
- **Test:** `tests/test_tensorfold_seamless.py::test_current_tensorfold_is_reused_without_reinstalling`

#### Scenario: install once, then reuse
Given  a Mac without TensorFold,
When   llgenie ensures it three times,
Then   the install step ran exactly once.
- **Test:** `tests/test_tensorfold_seamless.py::test_install_then_reuse_installs_exactly_once`

#### Scenario: a failed install fails loudly
Given  a Mac without TensorFold whose install fails,
When   llgenie ensures TensorFold,
Then   it exits non-zero, says FAIL,
And    writes no start script.
- **Test:** `tests/test_tensorfold_seamless.py::test_a_failed_install_fails_loudly_and_writes_no_start_script`

#### Scenario: a uv tool install outside PATH is found
Given  TensorFold at the pin in `~/.local/bin`, which is not on PATH,
When   llgenie ensures it,
Then   it is current and not reinstalled.
- **Test:** `tests/test_tensorfold_seamless.py::test_detect_finds_a_uv_tool_install_outside_path`

#### Scenario: the pick shows what will happen
Given  TensorFold absent / outdated / current on a 48 GB Mac,
When   `llgenie --select 1 --dry` plans the pick,
Then   the Engine line ends with `(installs X on pick)` / `(installed A -> updates to X on pick)` / `(installed X)`,
And    nothing is installed.
- **Test:** `tests/test_tensorfold_seamless.py::test_select_shows_what_picking_tensorfold_will_do`

#### Scenario: the pick installs TensorFold and serves through it
Given  a Mac without TensorFold and the TensorFold checkpoint local,
When   the user runs `llgenie --select 1 --engine tensorfold`,
Then   TensorFold is installed at the pin,
And    `tensorfold serve <checkpoint> --port <port> --name llm-local` is launched via the start script.
- **Test:** `tests/test_tensorfold_seamless.py::test_llgenie_pick_installs_tensorfold_then_execs_its_start_script`

#### Scenario: REAL install, update and reuse on Apple Silicon
Given  an Apple-Silicon Mac with real uv and an isolated uv tool dir,
When   the pick runs with TensorFold missing, then older, then current,
Then   it installs, updates and reuses the pinned TensorFold,
And    the start script prints the pinned version.
- **Test:** `tests/test_native_engine_real.py` via `make test-native-engine` (local host + CI job `native-engine-macos-arm64`)

#### Scenario: Metal TensorFold serves the 64K window Hermes Agent needs
Given  a 48 GB Apple-Silicon Mac and no LLGENIE_CONTEXT,
When   llgenie plans TensorFold's Metal launch,
Then   it passes `--context 65536` and sets TENSORFOLD_MEMORY_LIMIT_GB to the Mac's RAM,
And    the CUDA launch keeps TensorFold's own sizing.
- **Test:** `tests/test_tensorfold_seamless.py::test_metal_tensorfold_serves_a_64k_window_with_the_full_mac_budget`

#### Scenario: LLGENIE_CONTEXT overrides the TensorFold window
Given  LLGENIE_CONTEXT set to 131072 or 0,
When   llgenie plans TensorFold's Metal launch,
Then   that value is passed as `--context`,
And    0 leaves `--context` out, so TensorFold sizes the window to its budget (its own `--context 0` means unlimited on Metal).
- **Test:** `tests/test_tensorfold_seamless.py::test_llgenie_context_overrides_the_tensorfold_window`

#### Scenario: native engine targets only run on hardware that has a native engine
Given  a host that is not an Apple-Silicon Mac (every Linux CI job: cuda, rocm, vulkan, cpu),
When   `make test-native-engine` / `test-native-engine-serve` / `test-native-engine-light` / `test-interactive-tensorfold[-ci]` runs,
Then   it prints that native engines are Metal-only and that this host's engines are tested in their images,
And    exits 0 without running a Metal case; on an Apple-Silicon Mac the same targets run every case.
- **Test:** `make test-native-engine NATIVE_HOST=` (simulated non-Metal host) prints the note and exits 0; CI job `native-engine-macos-arm64` runs the cases

#### Scenario: interactive llgenie — pick Qwen3.8-27B, then TensorFold, from the printed lists
Given  a 48 GB Mac without TensorFold and Qwen3.8-27B's TensorFold checkpoint local,
When   the user runs plain `llgenie` and types the numbers the trend list and the engine list show for Qwen3.8-27B and TensorFold,
Then   TensorFold is in Qwen3.8-27B's engine list as `[metal]` with `(installs <pin> on pick)`,
And    the pick installs the pinned TensorFold and serves the checkpoint through the native start script.
- **Test:** `tests/test_tensorfold_seamless.py::test_interactive_llgenie_lists_pick_qwen38_27b_then_tensorfold_which_installs_and_serves` (make test-unit)

#### Scenario: REAL interactive llgenie on Apple Silicon serves Qwen3.8-27B with TensorFold
Given  an Apple-Silicon Mac without TensorFold (isolated uv tool dir),
When   plain interactive `llgenie` is driven in a terminal: Qwen3.8-27B picked from the trend list, TensorFold from its engine list,
Then   the real TensorFold install script installs the pin, the model is served on Metal,
And    it answers "hi" on `/v1/chat/completions` (on the 7 GB macOS CI runner: the same picks with `--dry` on an emulated 48 GB Mac, the real install, and the start script's pinned version).
- **Test:** `tests/test_interactive_tensorfold_real.py` via `make test-interactive-tensorfold` (local host; `TEST_LAUNCHER=~/bin/llgenie` after `make install`) and `make test-interactive-tensorfold-ci` (CI job `native-engine-macos-arm64`)

#### Scenario: REAL pick downloads, installs and serves on Metal
Given  an Apple-Silicon Mac without TensorFold and an empty ~/models,
When   `llgenie --select 1 --engine tensorfold` runs,
Then   TensorFold is installed, Qwen3.8-27B's TensorFold checkpoint is downloaded, the model is served on Metal
       with `--context 65536` (TensorFold reports `context: 65536`),
And    it answers "hi" on `/v1/chat/completions`.
- **Test:** `tests/test_native_engine_real.py::test_5_llgenie_pick_downloads_installs_and_serves_on_metal` via `make test-native-engine-serve` (local Apple-Silicon host)

#### Scenario: the lightest TensorFold model on the macOS arm64 runner
Given  an Apple-Silicon host and the lightest checkpoint TensorFold 0.6.5 serves (`mlx-community/Qwen3.5-9B-MLX-4bit`, 5.5 GiB),
When   TensorFold is ensured at the pin and the model is served through llgenie's start script,
Then   on a host whose TensorFold plan fits it, it is served on Metal and answers "hi",
And    on a host too small for it (GitHub's 7 GB `macos-15` runner) TensorFold's plan and the start script refuse it with the budget, without hanging.
- **Test:** `tests/test_native_engine_light.py` via `make test-native-engine-light` (local host; `LLAMA_RAM_BYTES=7516192768` proves the runner branch) and CI job `native-engine-macos-arm64`

### Requirement: the trend list meets its acceptance criteria on Linux and Mac hardware
For every host in the matrix (linux cuda 8/16/24, rocm 16/24, vulkan 16/48, cpu 16/48;
mac metal 16/48/128 GB) the list MUST satisfy AC1–AC8: README rows that fit, in README
order (AC1); numbering 1..N over servable rows, with `--select N` / `--auto` taking that row
(AC2); every engine is this host's variant or cpu, never disabled or another backend's
(AC3); ranking same hardware → other → supported, then t/s (AC4); every engine has a
fitting plan or local copy, and TensorFold only its own checkpoints (AC5); unservable rows
say why and offer nothing (AC6); the t/s label has a `(Backend)` suffix only for other
hardware (AC7); the header names backend and card (AC8).

WHEN llgenie builds the list on any supported hardware
THEN AC1–AC8 hold.

#### Scenario: the README parser is the registry list
Given  the vendored README,
When   its table is parsed,
Then   it equals the registry's names and VRAM tiers in order.
- **Test:** `tests/test_trend_list_acceptance.py::test_readme_parser_reads_the_vendored_list`

#### Scenario: AC1 rows
Given  the README list and each host of the matrix,
When   llgenie builds its list,
Then   it is exactly the README models whose VRAM fits, in README order.
- **Test:** `tests/test_trend_list_acceptance.py::test_ac1_rows_are_the_readme_models_that_fit_in_readme_order`

#### Scenario: AC3 engines run here
Given  each host's list,
When   every offered engine is checked,
Then   it is this host's variant or cpu, not disabled, never another backend's.
- **Test:** `tests/test_trend_list_acceptance.py::test_ac3_every_engine_runs_on_this_host`

#### Scenario: AC4 ranking
Given  each host's list,
When   each row's engines are read,
Then   they are ordered by rank then t/s, and rank 0 means measured on this hardware.
- **Test:** `tests/test_trend_list_acceptance.py::test_ac4_engines_are_ranked_same_hardware_then_other_then_supported`

#### Scenario: AC5 fit
Given  each host's list and weight budget,
When   each engine's source is resolved,
Then   a plan or local copy exists in a format it reads and the plan fits the budget,
And    TensorFold plans only TensorFold checkpoints.
- **Test:** `tests/test_trend_list_acceptance.py::test_ac5_every_engine_has_a_fitting_download_or_local_copy`

#### Scenario: AC6 reasons
Given  each host's list,
When   rows are split into servable and not,
Then   a row has engines exactly when it has no reason.
- **Test:** `tests/test_trend_list_acceptance.py::test_ac6_unservable_rows_say_why_and_offer_nothing`

#### Scenario: AC2 AC7 AC8 printed list
Given  each host's rows,
When   `llgenie --trend` prints them,
Then   the header names backend and card,
And    rows are numbered 1..N only where servable,
And    the t/s label carries `(Backend)` only for other hardware.
- **Test:** `tests/test_trend_list_acceptance.py::test_ac2_ac7_ac8_printed_list_numbering_labels_and_header`

#### Scenario: AC2 --select and --auto
Given  each 16/48 GB host's servable rows,
When   `--select 1`, `--select N` and `--auto` run dry,
Then   each takes exactly that row and its top engine,
And    `--select N+1` is refused with the valid range.
- **Test:** `tests/test_trend_list_acceptance.py::test_ac2_select_n_and_auto_take_the_numbered_row`

#### Scenario: each host gets its own top engine
Given  Qwen3.8-27B on a 48 GB Mac, a 24 GB cuda card and a 48 GB cpu host,
When   each top engine is read,
Then   the Mac runs TensorFold natively on a Metal figure,
And    the cuda card's top figure is CUDA,
And    the cpu host never gets TensorFold.
- **Test:** `tests/test_trend_list_acceptance.py::test_same_readme_different_hardware_gives_each_host_its_own_top_engine`
