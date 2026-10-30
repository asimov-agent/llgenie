# census-tree-at-sha

- [x] `scripts/check_architecture_census.py`: `measure(ref)` and `check()` count the tree at the doc's `measured at <sha>`, require it to be an ancestor of `HEAD`, and name both values on a stale claim
- [x] `tests/test_architecture_census.py`: five hermetic fixtures over a real scratch git repo; prove they fail on the old script and pass on the new one
- [x] `docs/ARCHITECTURE.md`: the structural-gates row states the referent (no census number moves)
- [x] `agent-wiki/` note + `docs/changes.d/` fragment, and `CHANGES.md` re-rendered with `make changes-index` (the unit suite asserts the rendered index links every note)
- [x] `make lint`, `make check-docs`, `make check-wiring`, `make test-unit` and `make openspec-validate NAME=census-tree-at-sha` green
