# Tasks: engine-tag-publish-178

- [x] `engine_image.push()` gains a `moving` gate: publishing only the pinned ref with a named #178 note; CLI `push --no-moving`
- [x] `engine_image.pull_published()` gains a `moving_check` gate: pin-alone verification with a named note; CLI `pull-published --no-moving`
- [x] `mk/engines.mk`: `MOVING_FLAG` (`MOVING=0|false` -> `--no-moving`) wired into `push-engine` and `published-engine-pull`
- [x] `engine-build.yml`: `moving_tags` input (default `true`); `push-engine` + published-leg steps export `MOVING=0` when `false`
- [x] `engine_build_trigger.py`: per-cell dispatch fields carry `moving_tags=false`; existing dispatch tests updated, not duplicated
- [x] New tests `tests/test_engine_tag_publish.py`: PR-scoped push (pin-only push, note), main push regression (all refs), PR-scoped pull mid-wave (passes), main pull mid-wave (still fails), workflow wiring
- [x] Full unit suite green via `make test-unit`
- [x] `make openspec-validate NAME=engine-tag-publish-178` exits 0
- [x] Wiki entry + changes.d fragment; issue #178 body synced to the six-section shape with proven ACs; PR opened with `closes #178`
