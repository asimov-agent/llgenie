# Make `make install` clone + build the right llama.cpp server per card spec

## Why

`llgenie` serves models via `llama-server`, which must be compiled for the
**right tree** (which llama.cpp fork) and the **right backend** (which hardware
accelerator) for the machine that runs it. Previously the installed binary was a
fixed prebuilt that did not match arbitrary hardware. The card size also changes
which tree is correct: an NVIDIA card with 24 GB VRAM or less must use the
**Prism** llama.cpp fork (which adds low-bit quant support so large models fit
small cards); anything above 24 GB uses the **stock upstream** fork. This change
makes `make install` (host) and the CI pipeline (all variants, in parallel) do
that selection and build the correct binary, cloning/pulling to the latest commit
and verifying it serves a real model.

The same change also sets the server context from the model that was loaded.
`-c` is that GGUF's `context_length` (Ternary Bonsai 2 is 262144), lowered
only when the q4_0 KV cache does not fit the card. The number passed as `-c`
is the runtime `n_ctx` a client compacts against before the window fills.

## What Changes

- Size `llama-server` `-c` from the selected GGUF's trained `context_length`,
  lowered only when the q4_0 KV cache does not fit card RAM. Hybrid models
  (Ternary Bonsai 2, `context_length` 262144) count full-attention layers only,
  so a 16 GB card keeps the full trained window. Unit tests cover this and run
  in the CI `unit` job (`make test-unit`).
- Add `scripts/detect_server.py` — a hermetic, mockable detector that calls the
  **real** system tools (`nvidia-smi`, `sysctl`, `/proc/meminfo`, `uname -m`,
  `shutil.which`) to pick (a) the **tree** from card RAM and (b) the **backend**
  from the hardware. Env seams let CI/tests force each value:
  - `LLAMA_BACKEND` = metal | cuda | cpu
  - `LLAMA_RAM_BYTES` = card RAM in bytes (test-only seam; the production input
    is the real card RAM — GPU VRAM when an NVIDIA card is present, else system RAM)
  - `LLAMA_SERVER_TREE` = prism | upstream (forces the tree, independent of RAM;
    this is the CI seam that lets each variant job verify a specific tree+backend
    combo regardless of the runner's actual card)
- Add `scripts/build_llama_server.sh <tree> <backend>` — the **single code path**
  (shared by host and CI) that:
  1. **clone-or-pull** the right tree to its **latest commit** (clone if absent;
     fetch + `reset --hard origin/<branch>` if present — never a stale prebuilt);
  2. builds in a **per-backend dir** (`build-cpu` / `build-cuda` / `build-metal`)
     so parallel variants never collide;
  3. verifies the binary exists and responds to `--help` (exit 0).
- Rewire `make install` to: detect tree+backend (auto, from the real card),
  run `build_llama_server.sh`, then `link` the binary into `~/bin/llama-server`
  and do the existing launcher/venv/smoke setup. If `$HOME/bin` is not already
  on `PATH`, add `export PATH="$HOME/bin:$PATH"` at the top of `~/.bashrc`
  when the login shell is bash, or `~/.zshrc` when it is zsh. An existing
  line is left unchanged.
- Add explicit variant targets `make install-prism-cpu`, `install-upstream-cuda`,
  etc., so each variant can be built in isolation (used by the host "right one
  only" path and by the parallel CI variant jobs).
- Add `tests/test_detect_server.py` — 27 hermetic unit tests covering the
  threshold (24 GB inclusive -> prism, 25 GB -> upstream), the backend detection
  (cuda needs nvidia-smi **and** nvcc; metal needs Apple Silicon), the tree
  override, and `detect_all` composition (build dir + cmake flags per variant).
- CI: a **`server-variants`** matrix (one GitHub job per variant, `fail-fast:
  false`) on **`ubuntu-latest`** that starts `prism+cpu` beside `prism+cuda` and
  stock `upstream+cpu` beside `upstream+cuda` (CUDA toolkit in the variant image
  before the compile), and a **`server-variants-mac`** matrix on **`macos-14`**
  that starts `prism+cpu` beside `prism+metal` and stock `upstream+cpu` beside
  `upstream+metal`. Each binary is checked for `--help`/`--version`. Every
  variant downloads the Qwen 0.5B GGUF and must answer `"hi"`. CUDA jobs also
  check `ldd`. `--n-gpu-layers` is not passed, so `llama-server` keeps its
  default and takes GPU or CPU, whichever it can.
- **Card-driven MTP spec-decode knobs** in `scripts/llama_serve.py` (issue #84,
  qwen38-mtp): `mtp_depth_for_card()` + `mtp_spec_flags()` set `--spec-type
  draft-mtp` (engaged iff the GGUF has `nextn_layers > 0`), `--spec-draft-n-max`
  card-class driven (`<=16` GB → 1, `16 < RAM <= 24` GB → 2, `>24` GB → 3), and
  pin `--parallel` to 1 when MTP is engaged (community rule 5). `--spec-draft-p-min`
  is never a default; emitted only when `LLAMA_SPEC_DRAFT_P_MIN` is set. 13
  hermetic mocked unit tests in `tests/test_llama_ai.py` cover every bin
  boundary and the p-min seam.
- README: document `make install` auto-detect, the explicit variant targets,
  the env seams, and the CI matrix.

## Capabilities

- **clone-build**: `make install` clones/pulls the right llama.cpp tree to the
  latest commit and builds it for the detected backend; never a stale prebuilt.
- **card-spec-tree**: 24 GB (inclusive) -> Prism; > 24 GB -> upstream.
- **backend-detect**: Metal on Apple Silicon; CUDA when nvidia-smi + nvcc present;
  CPU fallback.
- **ci-variants**: the CI pipeline builds every tree x backend variant the runner
  can support, in parallel, and verifies each binary.
- **detection-tests**: hermetic unit tests mock every real-tool probe so the
  decision logic is proven without hardware.

## Impact

`make install` now takes longer on first run (it clones + compiles llama.cpp). CI
gains a `build-variants` matrix (more minutes) that runs in parallel. No runtime
serving behavior change; the served model is the same — only the binary that
serves it now matches the hardware.
