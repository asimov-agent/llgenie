# tag-identity-repin-gate: the repin diff is image-tag identity, not params text (#2559)

Date: 2026-11-12. OpenSpec change: `tag-identity-repin-gate`. Issue: #2559.

## What changed

The merged-on-main pin-bump gate (`check_engine_pins_published`) and the pre-merge publisher
(`engine_build_trigger`) both diffed the params FILE only, but a published tag
`<pin8>-<hash8>-<variant>` hashes the params file AND the engine's `Dockerfile.<variant>` plus
`entrypoint.sh` + `engine_runner.py`. PR #2517 (36 Dockerfiles changed, 0 params, adding the
non-root `USER`) therefore moved all 28 committed engine×arch tag identities with an EMPTY
params diff — the gate saw "no repin", the PR merged without publishing, and main went red
(`linux / unit` 43149489329: `test_every_image_install_pulls_is_published`, 1 failed / 3629
passed; `registry-liveness` 43149489162: 28/28 committed pins unpublished).

## What was verified

- `scripts/check_engine_pins_published.py` gained `retagged_engine_ids(base)`: for every
  buildable engine×arch cell it compares the tag this tree publishes (`ei._current_tag`) with
  the tag `base` publishes (`ei._tag_at`) and names every engine whose cells differ; first
  imports count too. `repinned_engine_ids` is now the union of that and the unchanged
  params-FILE diff — both the may-arm merge gate and the will-arm publisher inherit it, so a
  retagging PR is blocked until its exact tags resolve in GHCR and is the PR that publishes them.
- `tests/test_ci_publish_order.py::_deferred_engines` defers via the same shared helper
  (replacing its `engine_image.py`-text and per-Dockerfile text scans): a retagging PR defers
  retagged engines to `make ci-wait-engine-images`; a main run (base == head) retags nothing and
  still checks every tag.
- New hermetic fixtures (synthetic git repos with every hashed input) lock the behaviour:
  `test_retagged_engine_ids_names_an_engine_whose_dockerfile_changed_while_params_did_not`,
  `test_retagged_engine_ids_names_nothing_when_base_equals_head`,
  `test_repinned_engine_ids_is_the_union_of_params_and_tag_identity`,
  `test_a_tag_retagged_engine_dispatches_scoped_push_true`, and the two `_deferred_engines`
  Dockerfile/base==head scenarios. All pass; the only red test in the three suites is the
  live-GHCR `test_every_image_install_pulls_is_published`, which is the pre-existing red main
  state this change prevents from recurring (AC4/AC5 remediate the in-flight dispatches).
- No `.github/workflows/*.yml` changes: the `#823`/`#2504` text special cases are replaced by
  one shared computation rather than a second hand-rolled scan.

## Current status

Change files (`proposal.md`, `specs/tag-identity-repin-gate/spec.md`, `tasks.md` with
Given/When/Then), the three touched modules, hermetic tests, and this note all land together.
`make openspec-validate NAME=tag-identity-repin-gate` runs in CI (no docker/node runtime in the
agent container) and must exit 0 before merge.
