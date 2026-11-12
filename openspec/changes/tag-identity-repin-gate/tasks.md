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
- [x] 10. `make openspec-validate NAME=tag-identity-repin-gate` exits 0 with every task in this file
  ticked, the branch is pushed, and the PR body carries `closes #2559` plus the `AGENTS:`/`BASE:` pair
  from `make bot-stamp-body` (proven: `make openspec-validate NAME=tag-identity-repin-gate` rc=0;
  `make bot-stamp-body` stamped the pair `AGENTS: aa700cf2709485c4bc73778c3466405151e373dd 92544b 1373l`
  + `BASE:` and `make check-pr-agents-line PR_BODY=<pr body> PR_BASE=origin/main` → "OK: the AGENTS:
  line is reachable from both head and base", rc=0). (PR CI-green / mergeStateStatus CLEAN /
  auto-merge-armed are the standing loop duties tracked by `ci-verdict` + auto-merge on PR #2560 and
  by #2529 for the dispatch sweep — not a task this change can tick itself.)
