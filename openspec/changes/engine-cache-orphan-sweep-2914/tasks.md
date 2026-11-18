# Tasks

- [x] Factor the engine build's registry cache refs into a single `engine_image.cache_ref(image_name, variant)` seam that `build_base` and `build` call; behavior byte-identical to the pre-change fixed names (proven: existing `tests/test_engine_force_rebuild.py` + `tests/test_ci_images.py` cache-ref asserts still pass — 71 passed).
- [x] Add `scripts/cache_orphan_report.py` deriving the LIVE producer set from the ONE seams (`engine_image.cache_ref`, `ci_images.cache_ref`) and enumerating the org's `llgenie/` container packages via `gh api`; a fixed tag is an orphan only when it exists AND no seam writes it.
- [x] Hermetic unit tests `tests/test_cache_orphan_report.py` (registry seam stubbed, producer seams real): zero orphans while keying has not landed; an old-engine fixed tag is reported alone; the live set spans helpers/bases/cells; a sweep never returns a live fixed tag — 75 passed across the three suites on the host.
- [x] Make targets `engine-cache-orphan-report` / `engine-cache-orphan-sweep` in `mk/engines.mk`, both added to `.PHONY`; the target help lines claim no CI coverage (host tool against the org registry).
- [x] Docs trio: this OpenSpec change + `docs/ENGINES.md` GC section + the `agent-wiki` record for this issue; documentation is part of the change.
