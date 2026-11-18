# Tasks

- [x] 1. `scripts/registry_cache_orphans.py` exists: candidate derivation from `ci_images.IMAGES` +
      `engine_skills.BACKENDS` + `engine_image.matrix()`, `report`/`gc` modes, the
      `ORPHAN_TAG_RE` delete-guard, digest→version-id lookup, and the `scripts/proc.py` seam as its
      only subprocess path
- [x] 2. `make registry-cache-orphans` and `make registry-cache-gc` exist in `mk/engines.mk`;
      `make check-wiring` sees the script wired and `tests/test_registry_cache_orphans.py` present
- [x] 3. Hermetic tests green: candidate coverage of every helper/backend/matrix pair, all-candidates-
      match-the-orphan-shape, guard refuses content-keyed and ordinary tags, `gc` dry-run without
      `--yes` deletes nothing, injected-seam `gc --yes` deletes exactly the orphans and verifies zero
      remain (`make test-unit` / `pytest tests/test_registry_cache_orphans.py`)
- [x] 4. `make check-proc-gate`, `make check-package-layers`, `make check-ci-discipline` exit 0 with
      the new script/targets (no workflow invokes `registry-cache-gc`)
- [x] 5. The live report at a main head after both cache-keying changes prints the known orphans
      (`test/openspec/agent:buildcache`, `base-cpu|cuda|rocm|vulkan:buildcache`,
      `vllm:buildcache-cpu`) — measured 8 at filing; count may only shrink
- [x] 6. Docs: `agent-wiki/2026-11-18-registry-cache-gc-2914.md` + `docs/changes.d/` fragment +
      `make changes-index` CHANGES.md row, naming #2914 and PR; `make check-docs` green
- [x] 7. `make openspec-validate NAME=registry-buildcache-gc-2914` exits 0
- [x] 8. Gates green at the pushed head: `make test-unit` rc=0 (4051 passed, 972.7s) and
      `check-wiring`/`check-proc-gate`/`check-package-layers`/`check-ci-discipline`/`check-docs`/`lint`
      rc=0 at `5da144503b254a3623f4ec006f87719ac3dda316`; the PR carries `closes #2914` and the
      acceptance mirror. (The post-merge human-side `make registry-cache-gc` + zero re-report is the
      remaining AC2 evidence stamped on #2914 after auto-merge — the sweep action itself is never a
      tasks.md item.)
