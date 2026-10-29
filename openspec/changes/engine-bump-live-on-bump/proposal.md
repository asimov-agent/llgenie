# engine-bump-live-on-bump — proposal

Issue: [#995](https://github.com/asimov-agent/llgenie/issues/995)

## Why

`ci.yml` calls `pipeline.yml`, and that pipeline's `unit` job runs
`make test-engine-bump-live` on every Linux CI run. The target downloads the pinned
TensorFold release archive, checks its checksum, unpacks it, and runs the binary.
Measured on `896e5df2`, and unchanged on `8e1eb009`: the step is the `unit` job, and
`engine-bump.yml` never runs it. That workflow is the one that writes the new parameter
list (`make engine-bump` → pin, derive, apply, `generate-engine-params`) and opens the
PR whose CI builds that engine's images.

## What Changes

- Remove `make test-engine-bump-live` from the `pipeline.yml` unit job.
- Run it in `engine-bump.yml` after `make engine-bump` and the documentation review,
  and before the bump PR opens, only when `matrix.id == 'tensorfold'`.
- That row sets up Docker, runs `make test-env`, then the live target. The job can
  pull `llgenie/test` (`packages: read`). A failed archive proof does not open the
  TensorFold bump PR. Other engines skip the three steps and still open their PRs.
- The hermetic `tests/test_engine_bump.py` cases stay on `make test-unit`. The three
  live node ids stay de-selected there.

## Impact

- Affected: `.github/workflows/pipeline.yml`, `.github/workflows/engine-bump.yml`,
  `tests/test_engine_bump.py`, `docs/BOTS.md`, `docs/ARCHITECTURE.md`.
- `engine-bump-rebase.yml` only rebases open bump PRs. It does not write a pin.
- `engine-build.yml` builds images from committed params. It does not move a pin.
- The three live tests stay TensorFold-specific. A bump of another engine does not
  download that archive.
