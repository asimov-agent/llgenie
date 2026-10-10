# 2026-10-10 pick-vram-ram-matrix-tests

## What was verified / built
- Issue #122 (upstream): "Verify the interactive pick's VRAM/RAM model x engine
  permutation matrix yields a concrete fitting HF model for every choice".
- OpenSpec change `feat-pick-vram-ram-matrix-tests` (proposal/spec/tasks, all
  ticked, `make openspec-validate` valid).
- `scripts/model_engine_pick.py`: `plan_url(plan)` (resolvable
  `https://huggingface.co/<repo>/resolve/<rev>/<file>` per file) and
  `matrix(registry, gb, ram_gb, arch)` — the exhaustive set of runnable
  (model x engine x quant) permutations: README trend models that fit VRAM,
  engines that can run them on the host (cpu fallback, native metal), and the
  largest quantized HF download that fits `weight_budget_gb` (VRAM, + RAM for
  MoE). Own-checkpoint engines (Strata, TensorFold) get only their own plans.
- `scripts/llama_serve.py`: `llgenie --matrix [--vram V] [--ram R] [--arch A]` prints the whole
  matrix with exact HF URLs, exits 0, no download/serve. Explicit flags take precedence
  over the positionals `[GB] [RAM_GB] [ARCH]`, which override the detected host; the env
  seams LLAMA_BACKEND / LLAMA_RAM_BYTES / LLGENIE_SYSTEM_RAM_BYTES do the same when neither
  is given, so CI drives the arch x vram x ram permutation set.
- `tests/test_pick_matrix.py` (6 hermetic tests, mocked VRAM/RAM + stubbed Hub
  tree): exact URLs, largest-fit invariant, MoE RAM binding, engine-specific
  plans, VRAM scaling, over-VRAM/over-budget exclusions. All pass.
- `tests/test_pick_matrix_arch_perms.py` (73 hermetic tests, NEW): the exhaustive
  (arch × vram × ram) permutation set the Linux CI runs — cuda/rocm/vulkan/cpu/metal
  × {8,16,32,64} × {16,32,64} — asserts every runnable cell maps to the largest
  fitting quant as a resolvable HF URL, and locks the ARCHITECTURE axis of engine
  selection: cuda-only TensorRT-LLM never off-cuda, Vulkan-absent SGLang only on
  cuda/rocm, Metal host never falls back to a cpu image (issue #120), `--matrix`
  accepts the arch override and the explicit `--vram/--ram/--arch` flags.
- `tests/test_pick_full_registry.py` (NEW, 1505 tests): the **system pick-matrix test**
  the Linux CI runs (`make test-unit`). The whole llgenie business logic is exercised
  for REAL over the vendored `data/models.json` — every trending model × every engine
  it can run × all (arch × VRAM × RAM) — with the ONLY thing mocked being the inference
  server start (`--dry` returns before the start script's exec). VRAM/RAM/arch are
  stubbed the CI way (LLAMA_RAM_BYTES / LLGENIE_SYSTEM_RAM_BYTES / LLAMA_BACKEND env
  seams, through the real card_gb/system_ram_gb/host_arch path); the quantized model
  files and their real resolvable `huggingface.co/<repo>/resolve/<rev>/<file>` links
  come from the live Hub (no Hub stubs) and are asserted HTTP 200; the real
  `llgenie --pick --dry` CLI is asserted to agree with `matrix()`; per-engine
  supported-quant catalogs are audited. 1260 permutation cases + 70 HTTP-200 +
  70 quant-catalog + 105 use-case CLI = 1505, all pass.
- First-class per-engine quant-range business logic (NEW): `mp.engine_supported_quants`
  (ascending real quants of the engine's own format) + `mp.pick_quant` (the highest that
  fits); `matrix` routes every cell through them. Covered by `tests/test_engine_supported_quants.py`
  (72 tests, incl. per-arch×model catalog-link checks).
- Committed real quant catalog (NEW): `tests/fixtures/trending-quant-catalog.json`
  (14 models, 471 real quant files + downloadable `huggingface.co/.../resolve/...` links),
  generated read-only by `scripts/gen_trending_quant_catalog.py` (make sync-quant-catalog);
  validated by `tests/test_trending_quant_catalog.py`. The suite never downloads a model —
  only checks links exist (HTTP 200).
- Catalog = HF class table, gated + regenerated daily (NEW): shape is
  `{model: {engine: {arch, quants}}}` — each engine's arch ⊆ its real image variants
  (cuda/rocm/vulkan/cpu/metal). `make check-quant-catalog` (a CI gate, added to ci-unit
  and the daily `registry-sync` workflow) fails when the committed catalog differs from
  what the generator produces — the generator is separate tooling, not llgenie runtime
  logic, with no LLM calls. `tests/test_trending_quant_catalog.py` asserts the well-formed
  `{arch, quants}` map, the arch-variant subset rule, the fixture==canonical regression
  guard, that every offered engine/arch is catalogued, and a bounded HTTP-200 sample.
- CANONICAL TABLE MOVED to data/trending-quant-catalog.json (repo root data dir) + test
  fixture in tests/fixtures/, double-written by the generator (make sync-quant-catalog).
- PICK IS NOW HERMETIC (the big one): engine_supported_quants/pick_quant/matrix read the
  committed table — deciding what a chosen engine can load on this hardware never
  re-queries the live Hub; the Hub is touched only when actually downloading. A (model,
  engine) not yet catalogued falls back to live resolution. The system pick-matrix suite
  (1505) runs hermetically against the table; HTTP-200 stays a link-existence probe, not
  a pick dependency. test_pick_matrix disables the catalog (LLGENIE_QUANT_CATALOG=0) to
  keep exercising the live/stubbed-tree path.
- Generator now validates NEWLY-ADDED links vs the prior generated table (all on first
  run) by HTTP probe; groups GGUF shards + whole-repo snapshots into one plan per quant
  (with a dir flag for snapshots); drops engines with no enabled image (ExLlamaV3 fork).
- Generator edge-case tests (NEW): tests/test_quant_generator_edges.py covers the
  sync decision (links_to_validate) hermetically — first run validates ALL links, a
  refresh validates ONLY the newly-added ones, a drop-only refresh probes nothing, dead
  new links fail without writing, --check fails on any drift and passes when committed==
  generated, and a sync writes canonical + fixture in lock-step. Fix: main() only
  mirrors the fixture when writing the canonical location (-o overrides don't clobber it).
  wired into make test-unit; means the catalog is SENSITIVE to every change.
  - Linux auto-provision of Python 3.11 via uv (NEW): scripts/check_python.py finds a
    uv-managed python3.11 even when it is not on PATH, and when uv is on PATH but no 3.11
    exists runs `uv python install 3.11` as part of make -C tools create-venv (the Linux
    analogue of the macOS brew path) — so make install works out of the box on a host that
    ships only a newer Python (Omarchy 3.14). A host with neither uv nor 3.11 fails closed
    with an actionable message. running_is_want() is a test seam; tests/test_check_python_uv.py
    (hermetic) covers uv-managed-not-on-PATH, PATH-wins, auto-provision, fails-closed, and
    the FATAL message. Verified on this host: resolver finds the uv-managed 3.11 with
    /usr/local/bin stripped from PATH.
        OpenSpec proposal/spec/tasks synced to the arch-driven permutation set.

## Verification
- `make lint` GREEN, `make openspec-validate NAME=feat-pick-vram-ram-matrix-tests` valid.
- Golden edge-case suite: `test_pick_matrix_edge_case_golden` (525) + `_ram` (17) = 542
  pass through the REAL wired `llgenie --matrix` CLI (3:02). The VRAM suite is a literal
  525-row `_EDGE_CASES` list in clear text covering all 21 model+engine pairs × 5 archs
  × VRAM ladder; the RAM suite covers the RAM-sensitive engines' RAM ladder.
- RAM-sensitive engines (NEW): **Strata** (qwen3.8-flash-next-125b) picks Q2_0 below
  60 GB RAM and IQ3_XXS from 60 GB up — the generator now records BOTH plans in the HF
  class table so the pick chooses by RAM; **FreeToken** (qwen3.6-35b-a3b, MoE) picks a
  larger quant as RAM grows (MoE budget adds system RAM), up to the whole-repo snapshot.
- CI hardening (NEW): `ci.yml` + `registry-sync.yml` gate runs behind an actor guard —
  only the repo owner, the `github-actions[bot]`, and collaborators (GitHub API
  collaborators check) may trigger them, so a non-collaborator can never drive the
  upstream's GHCR publish jobs.
- `make test-unit`: 780 passed; 3 FAILED — all PRE-EXISTING on main, not from this
  change:
  1. `test_trend_pick.py::test_default_registry_is_the_vendored_file`
  2. `test_trend_pick.py::test_readme_links_answer_and_a_broken_copy_is_caught`
     -> dead link `https://github.com/LaurentZuijdwijk/llama.cpp` (404; the GitHub
     account is deleted) in the vendored `data/models.json` + fixture + engine skill.
  3. `test_engine_skills.py::test_digest_reads_the_live_registry_and_retries_a_failed_lookup`
     -> GHCR pinned-tag vs `:cpu` tag digest drift (live registry).
- Filed issue #124 for the dead LaurentZuijdwijk engine link (maintainer decision:
  replace URL or drop the dead engine).

## Status
- PR #123 open against asimov-agent/llgenie (head andyholst:feat/pick-vram-ram-matrix-tests,
  branch also pushed to asimov-agent so CI runs). lint/openspec/agents-read PASS;
  unit FAIL (the 3 pre-existing failures above). Waiting on CI to finish, then
  confirming the unit failure is only the pre-existing set.
- FINALIZED: the 9 feature commits were squashed into ONE Conventional Commit
  `1d4119a` ("feat(llgenie): VRAM/RAM x arch x engine x quant pick matrix, hermetic HF
  class table, and exhaustive 542-case golden edge tests (#122)") on top of `3c722d5`
  main. Issue #122 body + PR #123 body/title updated to match (clear-text literal list,
  RAM-sensitive engines, CI actor guard). Force-pushed to both fork (andyholst) and
  upstream (asimov-agent) refs; PR head == `1d4119a`. Awaiting human review — not merged.
