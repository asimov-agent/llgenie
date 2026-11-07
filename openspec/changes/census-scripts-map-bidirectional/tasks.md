# Tasks — census-scripts-map-bidirectional

- [x] 1. `openspec/changes/census-scripts-map-bidirectional` — proposal + `specs/architecture-census/spec.md` (G/W/T) + this checklist, written before any code (done pre-implementation)
- [x] 2. `scripts/check_architecture_census.py` — add `_coverage_problems(ref)` (tree ⊆ named), `_scripts_coverage_names` (basename + `scripts/`-prefixed + hyphenated spellings) and `_SCRIPTS_MAP_EXEMPT` (`__init__.py`); wire the coverage finding into `check()`; make `_referent_problems` read the section with the hyphen-aware extractor so `fold-live-profile.py` is not reduced to a phantom `profile.py`
- [x] 3. `docs/ARCHITECTURE.md` — map every previously-unmapped `scripts/*.py|.sh` module into its §Scripts group row (or the trailing shell-leg prose), so the tree has no reverse-direction finding at the census referent
- [x] 4. `tests/test_architecture_census.py` — negative control: a tree module with no group row reddens the gate naming it; the existing subset test stays green
- [x] 5. `agent-wiki/` + `docs/changes.d/` + `CHANGES.md` — the #1123 change-note trio
- [x] 6. Verified: `make check-architecture-census` exits 0 on the mapped tree (coverage=0, referent=0); the negative-control test exits 1 naming the orphan module; `make check-docs`, `make openspec-validate NAME=census-scripts-map-bidirectional` both exit 0
