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

- [x] 5.1 Add a parallel `server-variants` job (ubuntu-latest, CUDA+python image)
      and a `server-variants-mac` job (macos-14) using `LLAMA_SERVER_TREE` /
      `LLAMA_BACKEND` + `scripts/build_llama_server.sh`. Both jobs run in
      parallel; YAML validated against the full ci.yml.
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
      libs; CPU variants run the 0.5B "hi" health check. Metal on a non-macOS
      runner fails loudly (`build_llama_server.sh` preflight).

## README

- [x] 6.1 Document `make install` auto-detect, explicit variant targets, env
      seams, and the CI matrix — added "Which llama.cpp build is used (card-size
      rule)" section with the card-size table, backend matrix, variant targets,
      env seams, and CI matrix.

## Verification (final)

- [x] 7.1 All 4 host-buildable variants (upstream/cpu, upstream/cuda, prism/cpu,
      prism/cuda) built on the real host: binary exists, `--version` + `--help`
      exit 0, cuda binaries link cuda libs.
- [x] 7.2 `tests/test_detect_server.py` passes (27 tests).
- [x] 7.3 `make openspec-validate NAME=feat-server-clone-build` passes.
- [ ] 7.4 `make openspec-tasks-check` passes (all tasks ticked).
- [ ] 7.5 Full host loop green (`make loop`): lint, unit, install-host, health
      (answers "hi"), test, openspec all PASS.
- [ ] 7.6 Host acceptance: `make install` (auto-detects prism+cuda on this 16 GB
      NVIDIA card), then `llgenie --list` runs, then `make uninstall` + a fresh
      `make install` round-trips cleanly.
