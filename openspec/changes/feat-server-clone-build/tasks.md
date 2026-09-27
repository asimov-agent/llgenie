# feat-server-clone-build — Tasks

Checklist of record. Each step maps to a spec requirement in
`openspec/changes/feat-server-clone-build/specs/llama-server-build/spec.md`.
Ticked the moment the work is verified with real tool output.

## Detection (scripts/detect_server.py)

- [x] 1.1 Add `detect_backend()` calling real tools: `nvidia-smi -L` + `nvcc`
      (cuda), `sysctl hw.machinetype` / `uname -m` (metal), else cpu; overridden
      by `LLAMA_BACKEND`. Find `nvcc` in PATH and `/opt/cuda/bin` and
      `/usr/local/cuda/bin`.
- [x] 1.2 Add `detect_card_ram_bytes()`: `LLAMA_RAM_BYTES` override, else NVIDIA
      VRAM from `nvidia-smi --query-gpu=memory.total` when a GPU is present, else
      `sysctl hw.memsize` (macOS) / `/proc/meminfo` (Linux), else 48 GB.
- [x] 1.3 Add `choose_tree()` + `detect_all()`: 24 GB inclusive -> prism, > 24
      -> upstream; `LLAMA_SERVER_TREE` override; per-backend build dir + cmake
      flags; resolved binary path.
- [x] 1.4 Add CLI flags `--tree` / `--backend` / `--ram-gb` / `--json`.

## Build script (scripts/build_llama_server.sh)

- [x] 2.1 Single code path shared by host and CI: clone-or-pull the selected
      tree (`prism` -> PrismML-Eng branch `prism`; `upstream` -> ggerganov branch
      `master`) to its latest commit.
- [x] 2.2 Build in a per-backend dir (`build-cpu` / `build-cuda` / `build-metal`)
      so parallel variants never collide.
- [x] 2.3 Verify the binary exists and `--help` exits 0; for cuda, verify it
      links against CUDA runtime libs (`libcuda.so.1`/`libcudart`/`libcublas`).
- [x] 2.4 Loud toolchain preflight (git/cmake/g++; nvcc for cuda; macOS for metal)
      — never a silent skip.

## Makefile

- [x] 3.1 Rewire `make install` to auto-detect (tree + backend) then
      `scripts/build_llama_server.sh` + `link` the freshly-built binary, then
      existing launcher/venv/smoke. Verified on host (16 GB NVIDIA -> prism+cuda).
- [x] 3.2 Add explicit variant targets `install-prism-cpu`, `install-upstream-cpu`,
      `install-prism-cuda`, `install-upstream-cuda`, `install-prism-metal`,
      `install-upstream-metal`, and `build-variant TREE=<..> BACKEND=<..>`, each
      building one tree+backend in isolation. Verified: upstream+cpu, upstream+cuda,
      prism+cpu, prism+cuda all build and verify on the host.
- [x] 3.3 `make uninstall` removes exactly the launcher + symlinks it created
      (and now the cloned tree dirs `~/repository/git/{prism-llama.cpp,llama.cpp}`
      per #89 so CI jobs don't pollute the workspace); venv + repo source untouched;
      a fresh `make install` round-trips cleanly.
- [x] 3.4 Document the env seams and variant targets in the `help` target.

## Detection unit tests (tests/test_detect_server.py)

- [x] 4.1 Threshold: 24 GB inclusive -> prism; 25 GB -> upstream.
- [x] 4.2 Low-end (8/12/16 GB) -> prism; 64 GB -> upstream.
- [x] 4.3 `LLAMA_SERVER_TREE` override forces a tree independent of RAM; unknown
      override falls back to RAM.
- [x] 4.4 Backend: cuda needs nvidia-smi **and** nvcc; metal needs Apple Silicon;
      cpu fallback; `LLAMA_BACKEND` override wins; invalid override falls back.
- [x] 4.5 GPU VRAM (not system RAM) is the card RAM on an NVIDIA card.
- [x] 4.6 `detect_all` composition: build dir + cmake flags per variant; distinct
      dirs for cpu/cuda/metal.

## CI pipeline (.github/workflows/ci.yml)

- [x] 5.1 Add `server-variants` (ubuntu-latest, CUDA+python image) and
      `server-variants-mac` (macos-14). Each is a matrix of one job per
      variant so the prism pair and the stock pair start together
      (`fail-fast: false`, no `needs` between cells). Linux cells call
      `make install-<tree>-<backend>`; mac cells call
      `scripts/build_llama_server.sh`.
- [x] 5.2 `ubuntu-latest` job: builds upstream+cpu, upstream+cuda, prism+cpu,
      prism+cuda in the CUDA+python variant image (nvcc present, CUDA libs on
      PATH). The two CPU builds also run the 0.5B "hi" health check
      (`scripts/ci_health.py`) — proven in-container (prism+cpu -> "Hello! How
      can I assist you today?"). The two CUDA builds verify `--version`/`--help`
      (exit 0) and `ldd` links cuda runtime libs (proven on host with the same
      build; the in-container verification runs as a step in the job).
- [x] 5.3 `macos-14` job: builds upstream+metal, upstream+cpu, prism+metal,
      prism+cpu on Apple Silicon. The two CPU builds also run the 0.5B "hi"
      health check. (Requires the real macos runner in CI — cannot be exercised
      from a Linux host.)
- [x] 5.4 Each variant verifies its binary exists, `--version` returns a version
      string, and `--help` exits 0. CUDA variants assert `ldd` links cuda runtime
      libs. Every variant (cpu, cuda, and metal) downloads the Qwen 0.5B GGUF
      and asserts a non-empty reply to "hi". `--n-gpu-layers` is not passed, so
      `llama-server` keeps its default and takes GPU or CPU, whichever it can. Metal
      on a non-macOS runner fails loudly (`build_llama_server.sh` preflight).
- [x] 5.5 `tests/test_ci_variant_matrix.py` locks the four Linux pairs
      (`prism+cpu` with `prism+cuda`, `upstream+cpu` with `upstream+cuda`) and
      the four mac pairs (`prism+cpu` with `prism+metal`, `upstream+cpu` with
      `upstream+metal`) as matrix cells with `fail-fast: false` and no `needs`.
      The test is on the `make test-unit` list.
- [x] 5.6 `make serve-variant TREE=<tree> BACKEND=<backend>` serves an
      already-built binary on `PORT` or a free port. It does not rebuild,
      relink, or stop another llama-server. `--n-gpu-layers` is not passed.
      `tests/test_serve_variant.py` is on the `make test-unit` list.
- [x] 5.7 `make test-serve-variant` posts "hi" and then stops only the pid
      `make serve-variant` recorded. `make stop-serve-variant` is the same
      stop. A llama-server this Makefile did not start keeps running.

## README

- [x] 6.1 Document `make install` auto-detect, explicit variant targets, env
      seams, and the CI matrix — added "Which llama.cpp build is used (card-size
      rule)" section with the card-size table, backend matrix, variant targets,
      env seams, and CI matrix.

## Model context window (`scripts/llama_serve.py`)

- [x] 8.1 Read `context_length`, `attention.key_length`, `attention.value_length`,
      `full_attention_interval`, and `nextn_predict_layers` in both GGUF readers.
- [x] 8.2 `kv_bytes_per_token` charges only full-attention layers (interval + MTP
      block) and uses the header head dim. Dense models stay on `n_embd // n_head`
      for every block.
- [x] 8.3 `serve_context(meta, card_bytes)` is the only launch path for `-c`
      (`main` and `_serve_chosen`). Card RAM comes from
      `detect_server.detect_card_ram_bytes()` (VRAM when an NVIDIA card is
      present), not the hardcoded 48 GB constant.
- [x] 8.4 Unit tests in `tests/test_llama_ai.py` lock: Bonsai-shaped model on
      16 GB → 262144; same model on 8 GB → 30720; missing context_length →
      32768; fast reader keeps the hybrid fields. `_serve_chosen --dry` and
      `main --dry` print `-c` with that value. They run under `make test-unit`
      (CI job `unit` in `.github/workflows/ci.yml`).
- [x] 8.5 README launch section documents that `-c` follows the selected model's
      trained context, lowered only when the KV cache does not fit the card.


## MTP card-driven spec flags (`scripts/llama_serve.py`, issue #84 qwen38-mtp)

- [x] 9.1 Card-driven depth: `mtp_depth_for_card(card_bytes)` (8/12/16 GB -> 1,
      `<=24` GB -> 2, >24 GB -> 3; `<=16` / `<=24` inclusive bins, fallback to
      the largest bin) + `mtp_spec_flags(meta, card_bytes)` engaged iff
      `meta["nextn_layers"] > 0`, emitting `--spec-type draft-mtp` +
      `--spec-draft-n-max <card_depth>` and `--spec-draft-p-min` **only** via the
      `LLAMA_SPEC_DRAFT_P_MIN` seam (never a default).
- [x] 9.2 Wire into `build_command`: new `card_bytes=None` param (reads
      `detect_server.detect_card_ram_bytes()` when absent), call `mtp_spec_flags`,
      and pin `-np 1` when MTP is engaged (rule 5) — the size-based `-np`
      (2 slots `< 10 GB`) applies only when MTP is **absent**.
- [x] 10.1 `make install` runs `scripts/ensure_user_path.py`, which adds
      `export PATH="$HOME/bin:$PATH"` to `~/.bashrc` or `~/.zshrc` according
      to the login shell, and does not duplicate an existing line.
      `tests/test_ensure_user_path.py` is on `make test-unit`.
- [x] 9.6 A Prism low-bit file (`PTQ1_0`, `PQ2_0`, `TQ1_0`, `TQ2_0`) with no
      author sampling uses Bonsai defaults (`--temp 0.5`, `--top-p 0.85`,
      `--top-k 20`, `--min-p 0`). `-c`, `-ngl`, and the batch still follow
      that file and the card. Mocked `build_command` / `_serve_chosen` tests
      The mocked `llgenie` start (`subprocess.run` replaced) covers
      `PTQ1_0`, `PQ2_0`, `TQ1_0`, and `TQ2_0` at 2, 4, 8, 12, 16, 24, 32,
      48, 64, and 128 GB on CUDA, Metal, and CPU, plus a non-Prism Qwen2
      Q4 file at those same card sizes on all three backends.
      `llama-server` is not executed.
- [x] 9.5 `build_command` sets `-ngl`, `-fa`, `-ctk`/`-ctv q4_0`, and `-b`/`-ub`
      from the card and the backend, and emits `--jinja`, `--reasoning`, and
      MTP flags only when the loaded GGUF supports them. Hermetic tests in
      `tests/test_llama_ai.py` pass a mocked card and meta (no GPU, no server).
- [x] 9.3 13 hermetic mocked unit tests in `tests/test_llama_ai.py` (MTP
      card-driven spec flags section): depth per card bin, `card_bytes=None`
      falling back to the card-RAM seam, no spec flags when `nextn_layers == 0`,
      card-driven `n-max` in `build_command`, `p-min` absent by default / emitted
      only via `LLAMA_SPEC_DRAFT_P_MIN`, `-np 1` pinned for MTP even at small
      size, size-based `-np` retained for non-MTP, and `card_bytes=None`
      auto-detecting via `detect_card_ram_bytes`.
- [x] 9.4 Document the card-driven MTP rules in the OpenSpec
      `feat-server-clone-build` spec + proposal + README.

## Verification (final)

- [x] 7.1 All 4 host-buildable variants (upstream/cpu, upstream/cuda, prism/cpu,
      prism/cuda) built on the real host: binary exists, `--version` + `--help`
      exit 0, cuda binaries link cuda libs.
- [x] 7.2 `tests/test_detect_server.py` passes (27 tests).
- [x] 7.3 `make openspec-validate NAME=feat-server-clone-build` passes.
- [x] 7.4 `make openspec-tasks-check` passes (all tasks ticked).
- [x] 7.5 CI pipeline green for this change: lint, unit, install, cpu-health,
      openspec, and the variant jobs. prism+cuda and upstream+cuda compile
      llama-server in the prebuilt-CUDA image and answer "hi".
- [x] 7.6 Host acceptance: `make install` (auto-detects prism+cuda on this 16 GB
      NVIDIA card), then `llgenie --list` runs, then `make uninstall` + a fresh
      `make install` round-trips cleanly.
