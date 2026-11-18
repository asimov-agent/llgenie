# Registry cache GC sweep — superseded fixed-name buildcache tags (issue #2914)

## What was built

`scripts/registry_cache_orphans.py` (wired as `make registry-cache-orphans` / `make
registry-cache-gc` in `mk/engines.mk`) sweeps the GHCR cache namespaces the two content-keying
changes retired: `llgenie/<helper|base>:buildcache` (#2911/PR #2915) and
`llgenie/<engine>:buildcache-<variant>` (#2891/PR #2912). Candidates are DERIVED, not hardcoded —
`ci_images.IMAGES` + `engine_skills.BACKENDS` + `engine_image.matrix()` — so new engines/helpers join
the sweep automatically (38 candidates today). The `ORPHAN_TAG_RE` delete-guard accepts only
`^buildcache(-[a-z0-9]+)?$`: content-keyed cache refs and ordinary tags can never be deleted. Deletion
resolves the GHCR version id by digest and re-verifies zero remain. Subprocess calls ride the
`scripts/proc.py` seam.

## Verified

- Hermetic tests `tests/test_registry_cache_orphans.py` — 8 cases, every registry probe injected.
- Live report at this head: exactly the 8 measured orphans (`test|openspec|agent:buildcache`,
  `base-cpu|cuda|rocm|vulkan:buildcache`, `vllm:buildcache-cpu`), `make registry-cache-orphans` rc=0.
- Gates: `check-wiring` (incl. `.PHONY` for both targets), `check-proc-gate`,
  `check-package-layers` (module registered in *Product path*; edges `→ ci_images`, `→ proc` stated),
  `check-ci-discipline` (no new clock, `registry-cache-gc` wired into NO workflow),
  `make openspec-validate NAME=registry-buildcache-gc-2914` rc=0.

## Decisions

- `gc` deletions are an EXPLICIT human-side action after merge (`make registry-cache-gc`), never CI:
  the main pipeline is tests-only (#2701) and registry mutation sits on the #746 admin boundary.
- The delete-guard is the safety contract: the sweep can prove orphans and remove exactly them; the
  keyed refs (`<hash>-buildcache`) are structurally unmatchable by the guard.

## Status

PR opened closing #2914. Task 8 (post-merge: run `make registry-cache-gc` once, re-report prints 0)
lands after CI auto-merges; the report count can only shrink from here.
