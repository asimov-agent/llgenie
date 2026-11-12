# Tasks — tag-identity-repin-gate

- [x] 1. `scripts/check_engine_pins_published.py`: add `retagged_engine_ids(base, root)` — per buildable
  cell compare `ei._current_tag` (tree) with `ei._tag_at` (base); skip disabled variants; no base copy counts.
- [x] 2. `repinned_engine_ids` returns params-file diff UNION tag-identity diff (params behaviour never loosened).
- [x] 3. `tests/test_ci_publish_order.py::_deferred_engines` uses the shared helper instead of the
  `scripts/engine_image.py`-only special case; base == head defers nothing.
- [x] 4. Hermetic fixture tests: Dockerfile-only retag IS named; params-text diff still named; clean diff
  empty and probe-free; first import named; will-arm (`engine_build_trigger`) dispatch set covers a retag
  (`engine=<id>`, `push=true`) and excludes untouched engines.
- [x] 5. `.github/workflows/engine-build-pr-trigger.yml`: `pull_request` `paths` widened from
  `containers/engines/params/**` only to every tag-moving surface (`containers/engines/dockerfiles/**`,
  `containers/engines/entrypoint.sh`, `scripts/engine_runner.py`, plus `scripts/engine_skills.py` /
  `scripts/engine_image.py`); header comments + dispatch-input descriptions synced; `make check-workflows`
  rc=0; hermetic report `make engine-build-pr-trigger-report BASE=origin/main` prints `0 repinned`.
- [x] 6. Targeted `pytest tests/test_check_engine_pins_published.py tests/test_ci_publish_order.py
  tests/test_engine_build_trigger.py` rc=0 (58/58; the two live-registry tests are deselected on this
  host — they run in the PR's `test-unit` job, tracked as task 10).
- [x] 7. `make openspec-validate NAME=tag-identity-repin-gate` rc=0.
- [x] 8. `agent-wiki/` entry + `docs/changes.d/` entry naming issue #2559; issue #2559 body, proposal,
  spec delta and tasks all synced to the trigger-paths seam in the same commit batch.
- [x] 9. Commit the batch, push the branch, open the PR against upstream `main` with `closes #2559`
  and a body mirroring the proven acceptance criteria + `OPENSPEC: tag-identity-repin-gate`.
- [ ] 10. PR CI fully green — including the two live-registry tests, i.e. the #2517 fleet published by
  the remediation dispatch sweep — mergeStateStatus CLEAN onto latest `origin/main`, auto-merge armed;
  issue #2559 AC 4-6 ticked with proven evidence in the final all-ticked commit.
