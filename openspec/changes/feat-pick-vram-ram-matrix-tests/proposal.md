# Verify the interactive pick's VRAM/RAM model×engine permutation matrix (issue #122)

## Why

The interactive `llgenie` picker already steps trend models (fit VRAM) → engines
(can run on this host) → one specific quantized HF model (largest that fits the
VRAM/RAM budget). But the combination is verified only piecemeal. Nothing proves
that for every amount of VRAM (and RAM where an engine or MoE model needs it) the
user can go *how much VRAM I have* → *this trending model* → *this engine* → *this
exact HF quant file* and that the file truly fits. This change adds an exhaustive,
mockable permutation matrix with concrete HF URLs and hermetic tests (mocked VRAM/
RAM) that assert every offered choice produces the most reasonable fitting quant —
and makes the whole pick logic testable end-to-end until the engine is about to start.

## What Changes

- New `scripts/model_engine_pick.py` functions (stdlib only):
  - `plan_url(plan)` — the resolvable `https://huggingface.co/<repo>/resolve/<rev>/<file>`
    for every planned file of a download plan.
  - `matrix(registry, gb, ram_gb=None, arch=None)` — the exhaustive set of runnable
    (model × engine × plan) permutations. `gb` = VRAM (card) GB, `ram_gb` = system
    RAM (defaults to the host's), `arch` = cuda/rocm/vulkan/metal/cpu (defaults to
    the host). Every model of the README trend list whose `vram_tier` fits `gb`,
    every engine with a runnable image variant for `arch` (cpu fallback, native
    metal) that reads the model's format (own-checkpoint engines Strata/TensorFold
    get only their own plans), each whose planned quant `size` is the **largest**
    within `weight_budget_gb(gb, is_moe, ram_gb, arch)` (dense = VRAM; MoE on GPU =
    VRAM + RAM−4). Rows carry `{model, engine, use_format, plan, url, size_gb}`.
    Models with no runnable engine or no fitting quant are returned with `why`.
  - `engine_supported_quants(model, engine, gb, ram_gb, arch)` + `pick_quant(...)` —
    first-class business logic: the real range of quants a chosen engine supports
    (ascending, engine-format-only, each a real resolvable HF plan) and the highest
    that fits. `matrix` routes every cell through the same path, so the matrix, the
    per-engine range, the highest-quant pick and the CLI share one code path.
- **Hermetic pick (the core):** the pick's COMPARISON path reads ONE committed HF
  class table `data/trending-quant-catalog.json` (model → engine → `{arch, real
  quant plans with their downloadable huggingface.co/<repo>/resolve/<rev>/<file>
  links}`) and never re-queries the live Hub to decide what a chosen engine can
  load; the Hub is touched only when actually downloading. A (model, engine) not
  yet catalogued falls back to live resolution.
- **HF class table generator** `scripts/gen_trending_quant_catalog.py`
  (`make sync-quant-catalog`): separate read-only tooling, NOT llgenie runtime
  logic, no LLM calls, never downloads a model. Writes the canonical `data/` table +
  its test fixture in lock-step; validates the NEWLY-ADDED links vs the prior
  generated table (all on first run) by HTTP probe; a dead new link fails the sync
  without writing. `make check-quant-catalog` is a CI gate (ci-unit + daily
  registry-sync); the fixture must exactly match the canonical table, so a link
  change or dropped section is a caught regression.
- `llgenie --matrix [--vram V] [--ram R] [--arch A]` in `scripts/llama_serve.py` — prints every
  permutation with its exact HF URLs and exits 0 (no download, no serve). The explicit
  flags take precedence over the positionals `[GB] [RAM_GB] [ARCH]`, which take
  precedence over the detected card / system RAM / architecture. The env seams
  `LLAMA_BACKEND` / `LLAMA_RAM_BYTES` / `LLGENIE_SYSTEM_RAM_BYTES` override the
  detected host so CI drives the whole arch × vram × ram permutation set.
- **Linux Python-3.11 auto-provision** `scripts/check_python.py`: `make install` /
  `make -C tools create-venv` works out of the box on a host that ships only a newer
  Python (e.g. Omarchy 3.14) — finds a uv-managed python3.11 even when it is not on
  PATH, and when uv is on PATH but no 3.11 exists runs `uv python install 3.11` (the
  Linux analogue of the macOS brew path). A host with neither uv nor 3.11 fails
  closed with an actionable message.
- New tests (all wired into `make test-unit`, run on the Linux CI):
  - `tests/test_pick_matrix.py` — hermetic, stubbed Hub tree (deterministic
    sizes, no network), mocking VRAM and RAM. Asserts exact HF URLs, the
    largest-quant-that-fits invariant, engine-specific plans, MoE RAM binding,
    and the VRAM-scaling edges from issue #122.
  - `tests/test_pick_matrix_arch_perms.py` — the exhaustive (arch × VRAM × RAM)
    permutation test the Linux CI runs: for every key of the
    `cuda|rocm|vulkan|cpu|metal` × {8,16,32,64} × {16,32,64} grid it asserts that
    every runnable model × engine cell maps to the largest fitting quant as a
    resolvable HF URL, and locks the ARCHITECTURE axis of engine selection — a
    cuda-only engine (TensorRT-LLM) never appears off-cuda, a Vulkan-absent
    engine (SGLang) only on cuda/rocm, and a Metal host never falls back to a
    cpu image.
  - `tests/test_pick_full_registry.py` — the **SYSTEM pick-matrix test**: the whole
    llgenie business logic is exercised for REAL over the vendored `data/models.json`
    — every trending model × every engine it can run, over all (arch × VRAM × RAM),
    with the ONLY thing mocked being the inference server start. The VRAM / RAM /
    architecture are stubbed the CI way (the LLAMA_RAM_BYTES / LLGENIE_SYSTEM_RAM_BYTES
    / LLAMA_BACKEND env seams, through the real card_gb / system_ram_gb / host_arch
    detection path), while the quantized model files and their real resolvable
    `huggingface.co/<repo>/resolve/<rev>/<file>` links come from the committed HF
    class table (hermetic pick) and are asserted HTTP 200. The real
    `llgenie --pick --dry` CLI (returns before the start script's exec) is asserted
    to agree with `matrix()`, and per-engine supported-quant catalogs are audited.
  - `tests/test_engine_supported_quants.py` (72), `test_trending_quant_catalog.py`
    (6), `test_quant_generator_edges.py` (7), `test_check_python_uv.py` (5).

## Impact

- New: `openspec/changes/feat-pick-vram-ram-matrix-tests/specs/pick-vram-ram-matrix/spec.md`,
  `tests/test_pick_matrix.py`, `tests/test_pick_matrix_arch_perms.py`,
  `tests/test_pick_full_registry.py`, `tests/test_engine_supported_quants.py`,
  `tests/test_trending_quant_catalog.py`, `tests/test_quant_generator_edges.py`,
  `tests/test_check_python_uv.py`, `data/trending-quant-catalog.json`,
  `scripts/gen_trending_quant_catalog.py`.
- Changed: `scripts/model_engine_pick.py`, `scripts/llama_serve.py` (`--matrix`),
  `scripts/check_python.py` (uv auto-provision), `Makefile` (`test-unit` runs the new
  tests + `sync/check-quant-catalog`), `README.md` (`--matrix`, the HF class table,
  the uv auto-provision), `.github/workflows/registry-sync.yml` (regenerates the
  catalog daily).
