# feat-server-clone-build — spec of record

## ADDED Requirements

### Requirement: card RAM selects the llama.cpp tree
The build system MUST select the llama.cpp fork from **card RAM only**, never by
inspecting the downloaded model's quant/filename. "Card RAM" means the NVIDIA
GPU's VRAM when an NVIDIA card is present (`nvidia-smi --query-gpu=memory.total`),
otherwise the system RAM.

#### Scenario: 24 GB inclusive boundary picks Prism
- **Given** a card with exactly 24 GB of RAM (16 GB NVIDIA VRAM is also <= 24 GB)
- **When** the tree is selected from card RAM
- **Then** the tree is `prism` (inclusive lower bound)
- **Test:** `tests/test_detect_server.py::test_choose_tree_24gb_inclusive_is_prism`

#### Scenario: above 24 GB picks upstream
- **Given** a card with 25 GB (or 48 GB / 64 GB) of RAM
- **When** the tree is selected from card RAM
- **Then** the tree is `upstream`
- **Test:** tests/test_detect_server.py::test_choose_tree_25gb_is_upstream

#### Scenario: low-end cards pick Prism
- **Given** an 8 GB or 12 GB or 16 GB card
- **When** the tree is selected from card RAM
- **Then** the tree is `prism`
- **Test:** tests/test_detect_server.py::test_choose_tree_8gb_is_prism / test_choose_tree_16gb_is_prism

#### Scenario: GPU VRAM, not system RAM, is the card RAM on an NVIDIA card
- **Given** a machine with a 16 GB NVIDIA GPU and 64 GB of system RAM
- **When** card RAM is read
- **Then** the value is the GPU's VRAM (16 GB), yielding `prism`, not the 64 GB
  system RAM value (which would yield `upstream`)
- **Test:** tests/test_detect_server.py::test_detect_card_ram_bytes_reads_nvidia_vram

### Requirement: hardware selects the backend
The build system MUST select the backend from the hardware using the real tools:
- **metal**: macOS + Apple Silicon (`sysctl hw.machinetype` / `uname -m`)
- **cuda**: `nvidia-smi -L` lists a GPU **and** `nvcc` (the compiler) is installed
- **cpu**: fallback (no usable GPU path)

#### Scenario: cuda requires both a GPU and nvcc
- **Given** an NVIDIA GPU is listed by `nvidia-smi` but `nvcc` is NOT installed
- **When** the backend is detected
- **Then** the backend is `cpu`, not `cuda`
- **Test:** tests/test_detect_server.py::test_detect_backend_cuda_requires_nvcc

#### Scenario: cuda when both are present
- **Given** `nvidia-smi -L` lists a GPU and `nvcc` is on PATH (or in
  `/opt/cuda/bin` / `/usr/local/cuda/bin`)
- **When** the backend is detected
- **Then** the backend is `cuda`
- **Test:** tests/test_detect_server.py::test_detect_backend_cuda_when_nvidia_and_nvcc

#### Scenario: metal on Apple Silicon
- **Given** macOS with Apple Silicon (`sysctl hw.machinetype = arm64`)
- **When** the backend is detected
- **Then** the backend is `metal`
- **Test:** tests/test_detect_server.py::test_detect_backend_metal_on_apple_silicon

#### Scenario: CPU fallback
- **Given** a machine with no NVIDIA GPU and no Metal path
- **When** the backend is detected
- **Then** the backend is `cpu`
- **Test:** tests/test_detect_server.py::test_detect_backend_cpu_when_no_nvidia

### Requirement: env seams for detection
The detection MUST expose three env-var seams (mock the hardware without
touching it), used by tests and the parallel CI variant jobs:
- `LLAMA_BACKEND` = metal | cuda | cpu
- `LLAMA_RAM_BYTES` = card RAM in bytes
- `LLAMA_SERVER_TREE` = prism | upstream (forces the tree, independent of RAM)

#### Scenario: backend override
- **Given** `LLAMA_BACKEND=cuda` is set
- **When** the backend is detected
- **Then** the backend is `cuda` regardless of the real hardware
- **Test:** tests/test_detect_server.py::test_detect_backend_override_wins

#### Scenario: tree override forces a tree independent of RAM
- **Given** an 8 GB card (which would normally pick `prism`) with
  `LLAMA_SERVER_TREE=upstream`
- **When** the tree is selected
- **Then** the tree is `upstream`
- **Test:** tests/test_detect_server.py::test_choose_tree_override_forces_tree_independently_of_ram / test_detect_all_tree_override_independent_of_ram

#### Scenario: unknown override falls back to RAM
- **Given** `LLAMA_SERVER_TREE=not-a-tree` on an 8 GB card
- **When** the tree is selected
- **Then** the RAM-based decision stands (`prism` for 8 GB)
- **Test:** tests/test_detect_server.py::test_choose_tree_unknown_override_falls_back_to_ram

### Requirement: clone-or-pull to the latest commit
The build MUST clone the selected tree if absent, or fetch and reset to the
branch tip if present. It MUST never build a stale prebuilt tree.

#### Scenario: fresh clone
- **Given** the selected tree directory does not exist
- **When** the build runs
- **Then** the tree is cloned at the latest commit of its branch
- **Test:** tests/test_ci_variant_matrix.py::test_build_script_clone_help_cuda_and_metal_contracts (asserts `git clone -b "$BRANCH"`)

#### Scenario: existing tree is pulled
- **Given** the selected tree directory already exists
- **When** the build runs
- **Then** the tree is fetched and reset to the branch tip before building
- **Test:** tests/test_ci_variant_matrix.py::test_build_script_clone_help_cuda_and_metal_contracts (asserts `git fetch origin` + `checkout -B`)

### Requirement: per-backend build dirs (parallel-safe)
Each backend build MUST write into its own per-backend dir (`build-cpu`,
`build-cuda`, `build-metal`) so parallel variants never collide.

#### Scenario: distinct build dirs
- **Given** the same card built for cpu, cuda, and metal
- **When** `detect_all` is run for each backend
- **Then** the build dirs are `build-cpu`, `build-cuda`, `build-metal`
  respectively, each with the matching CMake flags
- **Test:** tests/test_detect_server.py::test_detect_all_same_card_different_backend_different_dirs

### Requirement: build verifies the binary
The build MUST verify the resulting `llama-server` binary exists, responds to
`--help` (exit 0), and — for the cuda variant — links against CUDA runtime
libraries (`libcuda.so.1`, `libcudart`, `libcublas`).

#### Scenario: binary exists and --help works
- **Given** a successful build
- **When** the binary is checked
- **Then** the binary exists and `--help` exits 0
- **Test:** tests/test_ci_variant_matrix.py::test_build_script_clone_help_cuda_and_metal_contracts (asserts `"$BINARY" --help`)

#### Scenario: cuda binary links cuda libs
- **Given** a cuda variant build
- **When** the binary is checked for CUDA linkage
- **Then** it links against at least one CUDA runtime library
- **Test:** tests/test_ci_variant_matrix.py::test_build_script_clone_help_cuda_and_metal_contracts (asserts `libcudart`/`libcublas`)

### Requirement: CI builds every tree x backend variant the runner supports, in parallel
The CI pipeline MUST build and verify each supported tree x backend combination
as its own GitHub job (a matrix cell, not a later step in the same job). Cells
share no `needs` edge, and `fail-fast` is false, so one variant finishing or
failing does not cancel its pair. Each variant is self-contained (own runner,
own tree dir, own build dir).

- `server-variants` on `ubuntu-latest` (CUDA toolkit in the variant image
  before the compile) expands to four jobs that start together:
  `prism+cpu` with `prism+cuda`, and stock `upstream+cpu` with `upstream+cuda`.
- `server-variants-mac` on `macos-14` expands to four jobs that start together:
  `prism+cpu` with `prism+metal`, and stock `upstream+cpu` with `upstream+metal`.

#### Scenario: linux prism cpu and prism cuda start together
- **Given** the `server-variants` matrix on `ubuntu-latest`
- **When** GitHub expands the matrix
- **Then** `prism+cpu` and `prism+cuda` are two jobs with no `needs` between
  them, and `fail-fast` is false
- **Test:** tests/test_ci_variant_matrix.py::test_linux_prism_and_stock_pairs_are_parallel_matrix_cells

#### Scenario: linux stock cpu and stock cuda start together
- **Given** the `server-variants` matrix on `ubuntu-latest`
- **When** GitHub expands the matrix
- **Then** `upstream+cpu` and `upstream+cuda` are two jobs with no `needs`
  between them, and `fail-fast` is false
- **Test:** tests/test_ci_variant_matrix.py::test_linux_prism_and_stock_pairs_are_parallel_matrix_cells

#### Scenario: mac prism cpu and prism metal start together
- **Given** the `server-variants-mac` matrix on `macos-14`
- **When** GitHub expands the matrix
- **Then** `prism+cpu` and `prism+metal` are two jobs with no `needs` between
  them, and `fail-fast` is false
- **Test:** tests/test_ci_variant_matrix.py::test_mac_prism_and_stock_pairs_are_parallel_matrix_cells

#### Scenario: mac stock cpu and stock metal start together
- **Given** the `server-variants-mac` matrix on `macos-14`
- **When** GitHub expands the matrix
- **Then** `upstream+cpu` and `upstream+metal` are two jobs with no `needs`
  between them, and `fail-fast` is false
- **Test:** tests/test_ci_variant_matrix.py::test_mac_prism_and_stock_pairs_are_parallel_matrix_cells

#### Scenario: the CUDA toolkit is already in the image
- **Given** the variant image `gguf-tools/ci-variant`
- **When** a Linux variant stage starts
- **Then** `nvcc` and `libcudart` are already present from the prebuilt
  `nvidia/cuda` base image
- **And** the stage compiles `llama-server` inside that container
- **And** the stage does not install the CUDA toolkit and does not run a
  prebuilt `llama-server` image
- **Test:** tests/test_ci_variant_matrix.py::test_linux_variants_compile_llama_server_against_prebuilt_cuda (asserts `FROM nvidia/cuda`)

#### Scenario: each variant's binary is verified
- **Given** a variant build (tree + backend)
- **When** the build completes
- **Then** the binary exists, `--help` exits 0, and (for cuda) cuda libs are linked
- **Test:** tests/test_ci_variant_matrix.py::test_every_variant_runs_the_small_model_health_check

#### Scenario: a second variant server does not take another server's port
- **Given** a llama-server already listening, and a variant binary already built
- **When** `make serve-variant TREE=<tree> BACKEND=<backend>` runs
- **Then** it does not rebuild, does not stop the existing server, and binds
  `127.0.0.1` on `PORT` or on a free port when `PORT` is omitted
- **And** `--n-gpu-layers` is not passed, so `llama-server` keeps its
  default and takes GPU or CPU, whichever it can
- **Test:** tests/test_serve_variant.py::test_free_port_is_bindable_and_not_a_chosen_busy_port / test_taken_port_is_reported_not_free

#### Scenario: the variant server stops after the hi test
- **Given** a variant server started by `make serve-variant`
- **When** `make test-serve-variant` posts "hi"
- **Then** the reply is non-empty and `make stop-serve-variant` has stopped
  only that recorded pid
- **And** a llama-server that was not started by this Makefile keeps running
- **Test:** tests/test_serve_variant.py::test_stop_signals_only_the_recorded_pid

#### Scenario: every variant answers hi with the 0.5B model
- **Given** a finished variant binary (prism or upstream, cpu, cuda, or metal)
- **When** the CI health check downloads `Qwen2.5-0.5B-Instruct` q4_0 and POSTs "hi"
- **Then** `/health` is ok and the reply text is non-empty
- **And** `--n-gpu-layers` is not passed, so the server takes GPU or CPU,
  whichever it can
- **Test:** CI jobs `server-build-*` -> `make test-serve-variant TREE=… BACKEND=…`; contract: tests/test_ci_variant_matrix.py::test_every_variant_runs_the_small_model_health_check

#### Scenario: metal builds only on macOS
- **Given** a metal variant build on a non-macOS runner
- **When** the build attempts the metal backend
- **Then** it fails loudly with a clear "Metal requires macOS" error (no fake pass)
- **Test:** tests/test_ci_variant_matrix.py::test_build_script_clone_help_cuda_and_metal_contracts (asserts "metal requires macOS")

### Requirement: host `make install` builds only the right variant
The host `make install` MUST use the **auto-detected** tree + backend for the
real card (clone-or-pull + build + symlink), not a prebuilt. A host with a
16 GB NVIDIA card builds `prism + cuda` exactly once.

#### Scenario: host auto-detects and builds the right variant
- **Given** a host with a 16 GB NVIDIA GPU + nvcc
- **When** `make install` runs
- **Then** it detects `prism + cuda` and builds exactly that variant, symlinking
  `~/bin/llama-server` to the freshly-built binary
- **Test:** CI job `install` -> `make install`; contract: tests/test_ci_variant_matrix.py::test_install_ci_runs_make_install_and_make_uninstall

### Requirement: `make install` is locally testable
`make install` MUST be tested on the actual host as an acceptance criterion, and
`make uninstall` must remove exactly what `make install` created (launcher,
symlinks) without deleting repo source.

#### Scenario: uninstall removes only what install created
- **Given** a completed `make install`
- **When** `make uninstall` runs
- **Then** `~/bin/llgenie`, `~/bin/llgenie.py`, and `~/bin/llama-server` are
  removed, the venv and repo source files are untouched, and a fresh
  `make install` works
- **Test:** tests/test_ci_variant_matrix.py::test_uninstall_removes_install_artifacts_and_not_repo_source

### Requirement: the selected model's trained context is the server window
When `llgenie` starts `llama-server` for the model the user selected, `-c`
MUST be that model's maximum context, reduced only when the card cannot hold
the KV cache for it.

The ceiling is the selected GGUF's `<arch>.context_length`. Ternary Bonsai 2
(`sudoingx/Ternary-Bonsai-2-27B-PTQ1_0-MTP-GGUF`, architecture `qwen35`)
publishes `context_length` **262144**. On a 16 GB card the KV cache for that
window fits, so `-c` is **262144**. On an 8 GB card the same file does not
fit at 262144, so `-c` is **30720**.

The budget is card RAM from `detect_server.detect_card_ram_bytes()` (NVIDIA
VRAM when a GPU is present, otherwise system RAM; `LLAMA_RAM_BYTES`
overrides), minus the weight file and a 3 GB reserve. It is not the hardcoded
48 GB `TOTAL_RAM_BYTES` constant. Hybrid models that publish
`<arch>.full_attention_interval` charge KV only for the full-attention layers
(language blocks divided by the interval, plus `<arch>.nextn_predict_layers`
when the file has an MTP block) and use `<arch>.attention.key_length` /
`value_length` as the head dimension. A dense model with no interval counts
every block, with head dim `n_embd // n_head`. The result is rounded down to
a multiple of 1024 and is never below 2048. A missing `context_length` caps
the window at 32768.

`main` and `_serve_chosen` both call `serve_context` and pass the result to
`llama-server` as `-c`. That `-c` is the runtime window (`n_ctx` on
`/props`). A client of this server, including the Hermes `local-llm` profile,
compacts against that runtime window: the profile's Jev engine threshold is
0.60 of the probed `n_ctx`, so compression runs before the prompt fills the
window `llgenie` allocated.

#### Scenario: Bonsai on a 16 GB card gets its trained 262144 window
- **Given** a GGUF shaped like Ternary-Bonsai-2-27B-PTQ1_0-mtp
  (`context_length` 262144, 65 blocks, `full_attention_interval` 4,
  `nextn_predict_layers` 1, key and value length 256, 4 KV heads, about 6.5 GB)
- **When** it is served on a 16 GB card
- **Then** `-c` is 262144
- **Test:** tests/test_llama_ai.py::test_serve_context_uses_model_max_when_the_card_fits

#### Scenario: a card that cannot hold the trained window gets a smaller context
- **Given** the same Bonsai-shaped model
- **When** it is served on an 8 GB card
- **Then** `-c` is 30720, which is below 262144, a multiple of 1024, and at least 2048
- **Test:** tests/test_llama_ai.py::test_serve_context_shrinks_when_the_card_cannot_hold_the_train_ctx

#### Scenario: a missing context_length caps at 32768
- **Given** a dense model whose header has no `context_length`
- **When** it is served on a 48 GB card
- **Then** `-c` is 32768
- **Test:** tests/test_llama_ai.py::test_serve_context_missing_train_ctx_caps_at_32768

#### Scenario: the header reader keeps the hybrid fields
- **Given** a qwen35 GGUF header with `context_length` 262144, `key_length` 256,
  `value_length` 256, `full_attention_interval` 4, and `nextn_predict_layers` 1
- **When** `read_model_meta_fast` parses it
- **Then** those fields are on the meta dict and `serve_context` on a 16 GB card
  returns 262144
- **Test:** tests/test_llama_ai.py::test_fast_reader_captures_hybrid_context_fields / test_hybrid_kv_counts_full_attention_layers_only

### Requirement: make install puts ~/bin on the default shell PATH
`make install` MUST ensure `export PATH="$HOME/bin:$PATH"` is in the rc file for
the login shell. bash uses `~/.bashrc`. zsh uses `~/.zshrc`. If that file
already exports `$HOME/bin` or `~/bin` on `PATH`, it is left unchanged. The
line is inserted at the top so it runs before an interactive-only return.

#### Scenario: bash gets ~/.bashrc
- **Given** a home directory whose `.bashrc` does not mention `$HOME/bin`
- **When** install ensures the path for `/bin/bash`
- **Then** `.bashrc` starts with `export PATH="$HOME/bin:$PATH"`
- **Test:** tests/test_ensure_user_path.py::test_bash_is_the_rc_for_the_bash_shell

#### Scenario: zsh gets ~/.zshrc
- **Given** a home directory and a zsh login shell
- **When** install ensures the path
- **Then** `.zshrc` has the export and `.bashrc` is not created
- **Test:** tests/test_ensure_user_path.py::test_zsh_is_the_rc_for_the_zsh_shell

#### Scenario: a second install does not duplicate the line
- **Given** a `.bashrc` that already exports `$HOME/bin`
- **When** install ensures the path again
- **Then** the file is unchanged
- **Test:** tests/test_ensure_user_path.py::test_existing_home_bin_line_is_left_alone

### Requirement: launch flags follow the card and what the model supports
`build_command` MUST set the performance flags from the same card RAM used for
`-c` and from fields on the loaded GGUF. A hermetic test passes a mocked card
and a mocked meta dict (no GPU, no server).

- On `cuda` or `metal`, `-ngl` is 99 when the weights and the q4_0 KV cache for
  the chosen `-c` fit after the 3 GB reserve. Otherwise `-ngl` is the fraction
  of `n_layer` the leftover bytes can hold. On `cpu`, `-ngl` is absent.
- `-fa on` is present only for `cuda` and `metal`.
- `-ctk` and `-ctv` are `q4_0`, the quant `serve_context` used.
- `-b`/`-ub` are 512/256 when the card is at most 8 GB, 2048/512 when it is
  at most 24 GB, and 4096/1024 above that.
- `--jinja` is present only when the meta has a chat template.
- `--reasoning` is present only when the chat template is a reasoning template.
- MTP flags are present only when `nextn_layers > 0`.

#### Scenario: a GPU card that fits the model offloads every layer
- **Given** a Bonsai-shaped model (about 6.5 GB, 65 layers) and `backend=cuda`
- **When** `build_command` runs on a 16 GB card with the served context
- **Then** the argv contains `-c 262144`, `-ngl 99`, `-fa on`, `-ctk q4_0`,
  `-ctv q4_0`, `-b 2048`, `-ub 512`, and `--jinja`
- **Test:** tests/test_llama_ai.py::test_build_command_offloads_every_layer_when_the_card_fits

#### Scenario: a card that cannot hold the weights offloads fewer layers
- **Given** the same model and `backend=cuda`
- **When** `build_command` runs on an 8 GB card
- **Then** `-c` is 30720 and `-ngl` is less than 99, and `-b`/`-ub` are 512/256
- **Test:** tests/test_llama_ai.py::test_build_command_offloads_fewer_layers_when_the_weights_do_not_fit

#### Scenario: a CPU backend does not request GPU features
- **Given** the same model and `backend=cpu`
- **When** `build_command` runs
- **Then** the argv contains neither `-ngl` nor `-fa`
- **Test:** tests/test_llama_ai.py::test_build_command_cpu_backend_skips_gpu_flags

#### Scenario: a Prism PTQ1_0 file on 16 GB keeps full context and Bonsai sampling
- **Given** a Bonsai-shaped file named `PTQ1_0` (about 5.93 GB, 65 layers, MTP head, chat template) and `backend=cuda`
- **When** `build_command` runs on a 16 GB card
- **Then** `-c` is 262144, `-ngl` is 99, `-fa on`, `-ctk q4_0`, `-ctv q4_0`,
  `-b 2048`, `-ub 512`, `--temp 0.5`, `--top-p 0.85`, `--top-k 20`,
  `--min-p 0`, and `--spec-draft-n-max 1`
- **Test:** tests/test_llama_ai.py::test_ptq1_0_on_16gb_keeps_full_context_and_bonsai_sampling

#### Scenario: the same PTQ1_0 file on 8 GB shrinks context and offload
- **Given** that PTQ1_0 file and `backend=cuda`
- **When** `build_command` runs on an 8 GB card
- **Then** `-c` is 30720 and `-ngl` is 49
- **Test:** tests/test_llama_ai.py::test_ptq1_0_on_8gb_shrinks_context_and_offload

#### Scenario: a Prism PQ2_0 file on 8 GB offloads fewer layers than PTQ1_0
- **Given** the same shape with a `PQ2_0` name and about 7.25 GB of weights
- **When** `build_command` runs on an 8 GB card with `backend=cuda`
- **Then** `-c` is 30720 and `-ngl` is 40
- **Test:** tests/test_llama_ai.py::test_pq2_0_on_8gb_offloads_fewer_layers_than_ptq1_0

#### Scenario: a mocked llgenie start does not execute llama-server
- **Given** a `PTQ1_0` Bonsai file and a mocked 16 GB CUDA card
- **When** `llgenie` main runs and `subprocess.run` is replaced
- **Then** the replaced call receives `-c 262144`, `-ngl 99`, `-b 2048`,
  `--temp 0.5`, and `--spec-draft-n-max 1`, and the real server is not started
- **Test:** tests/test_llama_ai.py::test_mocked_llgenie_start_ptq_uses_vram_and_does_not_exec

#### Scenario: mocked starts cover every Prism packing at every card size
- **Given** `PTQ1_0` and `TQ1_0` at 5.93 GB, and `PQ2_0` and `TQ2_0` at 7.25 GB
- **When** `llgenie` main runs with `subprocess.run` replaced, for each packing,
  on a mocked CUDA card of 2, 4, 8, 12, 16, 24, 32, 48, 64, and 128 GB
- **Then** each start is captured and not executed. The lighter packings are
  `-ngl 0/5/49` at 2/4/8 GB and `-c 188416` at 12 GB. The heavier packings are
  `-ngl 0/4/40` at 2/4/8 GB and `-c 107520` at 12 GB. All four are `-c 262144`
  and `-ngl 99` from 16 GB up, `--spec-draft-n-max 2` at 24 GB, and `-b 4096`
  with `--spec-draft-n-max 3` from 32 GB up. Bonsai sampling is on every row
- **And** the same four packings on Metal use the same argv as CUDA, and on
  CPU at every one of those card sizes they keep that `-c`, batch, and MTP
  depth and omit `-ngl` and `-fa`
- **Test:** tests/test_llama_ai.py::test_mocked_llgenie_start_each_prism_quant_at_each_vram

#### Scenario: a non-Prism model is swept the same way
- **Given** a stock Qwen2 7B Q4 file (about 4.68 GB, trained context 32768, no MTP head)
- **When** `llgenie` main runs with `subprocess.run` replaced on CUDA, Metal,
  and CPU at 2, 4, 8, 12, 16, 24, 32, 48, 64, and 128 GB
- **Then** `-c` stays 32768, `-ngl` is 0/3/27 at 2/4/8 GB and 99 from 12 GB up
  on CUDA and Metal, the generic `--temp 0.6` is used, and there is no
  `--spec-type`. CPU omits `-ngl` and `-fa`
- **Test:** tests/test_llama_ai.py::test_mocked_llgenie_start_stock_model_at_each_vram / test_mocked_llgenie_start_stock_model_on_cpu

#### Scenario: the packing is read from the file on disk
- **Given** a GGUF header written under `MODELS_ROOT` and named `PTQ1_0`
- **When** `llgenie` main scans that directory with `subprocess.run` replaced
- **Then** `-c` is the header `context_length` and `--temp` is `0.5`
- **And** a file in that directory whose name is not a Prism packing uses
  `--temp 0.6` instead
- **Test:** tests/test_llama_ai.py::test_mocked_start_reads_prism_quant_from_the_gguf_filename / test_mocked_start_reads_a_stock_file_without_prism_sampling

#### Scenario: the same mocked start on 8 GB shrinks the argv
- **Given** that `PTQ1_0` file and a mocked 8 GB CUDA card
- **When** `llgenie` main runs with `subprocess.run` replaced
- **Then** the argv has `-c 30720`, `-ngl 49`, and `-b 512`
- **Test:** tests/test_llama_ai.py::test_mocked_llgenie_start_ptq_on_8gb_shrinks_the_argv

#### Scenario: author sampling on a Prism file wins
- **Given** a `PTQ1_0` file whose meta already has `sampling.temperature`
- **When** `build_command` runs
- **Then** that temperature is passed and `--temp 0.5` is not
- **Test:** tests/test_llama_ai.py::test_prism_file_keeps_author_sampling_when_present

#### Scenario: flags that need model support are omitted when the file lacks them
- **Given** a model with no chat template, no reasoning template, and
  `nextn_layers == 0`
- **When** `build_command` runs
- **Then** the argv contains no `--jinja`, no `--reasoning`, and no
  `--spec-type`
- **Test:** tests/test_llama_ai.py::test_build_command_omits_flags_the_model_does_not_support

### Requirement: MTP (spec-decode) knobs are card-driven
When a model carries an MTP (multi-token-prediction) draft head — detected as
`meta["nextn_layers"] > 0` in the GGUF (`nextn_predict_layers`), e.g.
Ternary-Bonsai-2 MTP / Qwen3.8-27B MTP — the launcher MUST engage `llama-server`'s
`--spec-type draft-mtp` path and set the community-mapped speed knobs from the
**card's RAM** (the same `detect_card_ram_bytes()` value that picks the tree),
never from hard-coded constants. Grounded in the qwen38-mtp community rules:

- **Depth (`--spec-draft-n-max`) is card-class driven.** `mtp_depth_for_card`
  returns `1` when card RAM `<= 16 GB` (8/12/16 GB — shallow: pays everywhere,
  no starved depth-2 risk), `2` when `16 GB < card RAM <= 24 GB` (24 GB
  inclusive), and `3` when card RAM `> 24 GB` (32/48/64/128/… GB). A hermetic
  unit test asserts each bin boundary against a mocked card-RAM seam (no real
  GPU required).
- **`--spec-draft-p-min` is never a default.** Emitted **only** when the seam
  `LLAMA_SPEC_DRAFT_P_MIN` env is set (community rule 2: it helps starved cards
  and hurts fast ones — a knob, never a constant). Unset => flag absent.
- **MTP pins `--parallel` to 1 regardless of model size.** When the MTP head is
  engaged, `-np 1` even for a small model (the size-based `-np 2` for models
  `< 10 GB` must NOT apply). When MTP is absent, the size-based rule stands:
  2 slots for models `< 10 GB`, 1 slot for `>= 10 GB`. (Community rule 5:
  speculative decode is a single-stream optimisation; `--parallel > 1` kills the
  gain and inflates the baseline.)

#### Scenario: a 24 GB card with an MTP model gets n-max 2
- **Given** a model with `nextn_layers > 0` served on a 24 GB card
- **When** `build_command` runs with `card_bytes = 24 * GiB`
- **Then** the argv contains `--spec-type draft-mtp`,
  `--spec-draft-n-max 2`, and `-np 1`
- **Test:** tests/test_llama_ai.py::test_mtp_depth_for_card_24_gb_is_2

#### Scenario: a small MTP model still pins -np 1 (rule 5)
- **Given** a model with `nextn_layers > 0` and `size_gb < 10` on a small card
- **When** `build_command` runs
- **Then** `-np 1` is emitted (the size-based `-np 2` for small models is
  suppressed because MTP is a single-stream path)
- **Test:** tests/test_llama_ai.py::test_build_command_mtp_pins_np_1_even_on_small_card

#### Scenario: p-min is off by default, on only via the seam
- **Given** an MTP model with `LLAMA_SPEC_DRAFT_P_MIN` unset
- **When** `mtp_spec_flags` runs
- **Then** no `--spec-draft-p-min` flag is present; with the seam set (e.g.
  `0.7`) the flag is emitted with that value
- **Test:** tests/test_llama_ai.py::test_mtp_spec_flags_p_min_off_by_default / test_mtp_spec_flags_p_min_emitted_only_when_env_set

#### Scenario: a model without an MTP head emits no spec flags
- **Given** a model with `nextn_layers == 0`
- **When** `build_command` runs
- **Then** the argv contains no `--spec-type` / `--spec-draft-n-max` /
  `--spec-draft-p-min` flags, and the size-based `-np` rule (2 slots `< 10 GB`)
  applies
- **Test:** tests/test_llama_ai.py::test_mtp_spec_flags_empty_when_no_nextn

#### Scenario: depth follows the same card RAM that picks the tree
- **Given** the same MTP model on an 8 GB card vs a 64 GB card
- **When** `build_command` runs for each card (card_bytes passed or detected via
  `detect_card_ram_bytes`)
- **Then** `--spec-draft-n-max 1` on the small card and `--spec-draft-n-max 3`
  on the large card — the knob is a function of the card, not a constant
- **Test:** tests/test_llama_ai.py::test_mtp_depth_for_card_falls_back_to_card_ram_seam / test_mtp_depth_for_card_16_gb_or_less_is_1 / test_mtp_depth_for_card_above_24_gb_is_3
