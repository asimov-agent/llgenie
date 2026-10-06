## ADDED Requirements

### Requirement: engines are ranked by reported t/s for this host
`rank_engines(model)` MUST return only engines that have a container image variant for
the host backend (cpu fallback), ordered by highest reported t/s, then trending
engagement. Measurements taken on Apple Silicon MUST NOT rank engines for a container host.

WHEN the engines of a model are ranked for a host
THEN the fastest runnable engine comes first.

#### Scenario: fastest runnable engine first
- **Given** qwen3.8-27b with t/s reported on several engines
- **When** it is ranked for a CUDA host
- **Then** every row is a cuda variant, t/s is descending, no Apple-Silicon row is used, and the LaurentZuijdwijk llama.cpp fork is first
- **Test:** `tests/test_model_engine_pick.py::test_engines_ranked_by_tps_then_trending_for_this_host`

### Requirement: only models that fit the card and have a runnable engine are offered
`rank_models()` MUST drop models whose `vram_tier` exceeds the card and models with no
runnable engine here, and order the rest by their best engine's t/s.

WHEN the registry is ranked for a card
THEN every offered model fits and has an engine.

#### Scenario: 8 GB CPU host
- **Given** an 8 GB CPU host
- **When** the registry is ranked
- **Then** no model above 8 GB is offered, each row has an engine, and t/s is descending
- **Test:** `tests/test_model_engine_pick.py::test_models_fit_the_card_and_need_a_runnable_engine`

### Requirement: model and engine come from parameters, a prompt, or the default
`--pick <model>` and `--engine <name>` MUST select by substring and fail on a miss.
With `--auto` or no terminal, llgenie MUST take the top model and its top engine without asking.

WHEN llgenie runs with `--auto`
THEN it picks the top model and engine without prompting.

#### Scenario: auto and parameter selection
- **Given** the ranked engines of qwen3.8-27b
- **When** auto, the parameter `sglang`, and the parameter `nope` are used
- **Then** auto returns the top row, `sglang` returns SGLang, and `nope` exits with an error
- **Test:** `tests/test_model_engine_pick.py::test_auto_takes_the_top_and_engine_param_selects`

### Requirement: a missing model is downloaded, a present one is reused
llgenie MUST serve a matching file under `~/models` when one exists, and download the
picked model otherwise, through the existing hf download path.

WHEN the picked model is not under `~/models`
THEN llgenie downloads it before serving.

#### Scenario: local file is reused
- **Given** a models dir with a Bonsai 2 27B GGUF
- **When** bonsai-2-27b is resolved
- **Then** that file is returned and nothing is downloaded
- **Test:** `tests/test_model_engine_pick.py::test_local_model_is_found_under_models_dir`

#### Scenario: CI downloads a real chunk
- **Given** a small GGUF repo on the Hub and `LLGENIE_DOWNLOAD_MAX_BYTES=1048576`
- **When** the model is downloaded for a 2 GB card
- **Then** the chosen `.gguf` lands in `~/models/<org>__<repo>/`, is exactly 1 MiB, and starts with the GGUF magic
- **Test:** `tests/test_model_engine_pick.py::test_download_fetches_a_real_chunk_of_the_chosen_file`

### Requirement: an exact local model file can be given
`--model-file <path>` MUST serve that file with the picked engine and never download.

WHEN `--model-file` is given
THEN that file is served as-is.

#### Scenario: exact Bonsai file on Prism
- **Given** a local `Ternary-Bonsai-2-27B-PTQ1_0-mtp.gguf`
- **When** `llgenie --pick bonsai --engine prism --model-file <file> --auto --dry` runs
- **Then** the command uses `llgenie-engine-llama-cpp-prism` with that exact file and nothing is downloaded
- **Test:** `tests/test_model_engine_pick.py::test_model_file_param_serves_that_exact_file`

### Requirement: the pick is served through the engine image
llgenie MUST serve the picked model with `~/bin/llgenie-engine-<id>` (written by
`make install`) on `127.0.0.1:<port>/v1` as `llm-local`.

WHEN `llgenie --pick --auto --engine vllm --dry` runs on an empty models dir
THEN it prints the vLLM pick, the download it would do, and the engine start-script command.

#### Scenario: dry run shows model, engine and container command
- **Given** the fixture registry, an empty models dir, and an 8 GB CPU host
- **When** `llgenie --pick --auto --dry --engine vllm` runs
- **Then** it exits 0, shows `Engine : vLLM [cpu]`, says it would download, and the command uses `llgenie-engine-vllm`
- **Test:** `tests/test_model_engine_pick.py::test_llgenie_dry_run_prints_model_engine_and_container_command`
