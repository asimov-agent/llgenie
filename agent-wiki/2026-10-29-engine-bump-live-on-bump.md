# engine-bump-live-on-bump — 2026-10-29

Implements **#995**. Pull request **#996**.

## What changed

`ci.yml` calls `pipeline.yml`. That file's `unit` job ran `make test-engine-bump-live`
on every Linux CI run. The target downloads the pinned TensorFold release archive,
checks its checksum, unpacks it, and runs `tensorfold-native --version`. Bumps do not
happen on that job. `engine-bump.yml` is the workflow that runs `make engine-bump`
(pin, derive, apply, `generate-engine-params`) and opens the PR whose CI builds the
engine images.

- The unit job no longer runs the live target. Hermetic `tests/test_engine_bump.py`
  cases stay on `make test-unit`. The three live node ids stay de-selected in
  `tests/fixtures/unit-suite.json`.
- The TensorFold row of `engine-bump.yml` sets up Docker, runs `make test-env`, then
  `make test-engine-bump-live`, after the new pin and the documentation review and
  before the PR step. The step is fatal, so a broken archive does not open that PR.
  Other engines skip those steps. The bump job has `packages: read` so it can pull
  `llgenie/test`.
- `engine-bump-rebase.yml` still only rebases open bump PRs. `engine-build.yml` still
  builds images from the committed params. Neither downloads the archive.

## Verified

`tests/test_engine_bump.py::test_unit_recipe_keeps_the_image_build_out` reads both
workflows: the unit job has no live step, and on the bump job Docker, `make test-env`,
and the live target sit between `make engine-bump` and the PR step, each gated on
`matrix.id == 'tensorfold'`.
