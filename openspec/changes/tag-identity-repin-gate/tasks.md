# Tasks — tag-identity-repin-gate

- [x] 1. `scripts/check_engine_pins_published.py`: add `retagged_engine_ids(base, root)` — per buildable
  cell compare `ei._current_tag` (tree) with `ei._tag_at` (base); skip disabled variants; no base copy counts.
- [x] 2. `repinned_engine_ids` returns params-file diff UNION tag-identity diff (params behaviour never loosened).
- [x] 3. `tests/test_ci_publish_order.py::_deferred_engines` uses the shared helper instead of the
  `scripts/engine_image.py`-only special case; base == head defers nothing.
- [x] 4. Hermetic fixture tests: Dockerfile-only retag IS named; params-text diff still named; clean diff
  empty and probe-free; first import named; will-arm (`engine_build_trigger`) dispatch set covers a retag
  (`engine=<id>`, `push=true`) and excludes untouched engines.
- [ ] 5. `make test-unit` rc=0 with the new tests; targeted `pytest tests/test_check_engine_pins_published.py
  tests/test_ci_publish_order.py tests/test_engine_build_trigger.py` rc=0.
- [ ] 6. `make openspec-validate NAME=tag-identity-repin-gate` rc=0 and `make openspec-tasks-check` rc=0.
- [ ] 7. `agent-wiki/` entry + `docs/changes.d/` entry naming issue #2559 and this PR; commit, push to the
  fork, open the PR against upstream `main` with `closes #2559`; drive it green and mergeStateStatus CLEAN.
