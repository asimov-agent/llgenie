# engine-bump-live-on-bump

## ADDED Requirements

### Requirement: the unit job does not download the release archive

The `pipeline.yml` `unit` job, which `ci.yml` calls on every pull request, MUST NOT
run `make test-engine-bump-live`.

WHEN a CI unit job runs
THEN it does not list, checksum, unpack, or execute the pinned TensorFold release archive.

#### Scenario: the unit job has no live archive step

- **Given** `.github/workflows/pipeline.yml`
- **When** the `unit` job steps are read
- **Then** no step runs `make test-engine-bump-live`
- **Test:** `tests/test_engine_bump.py::test_unit_recipe_keeps_the_image_build_out`

### Requirement: the bump pipeline proves the new TensorFold archive before the PR

`engine-bump.yml` MUST run `make test-engine-bump-live` after `make engine-bump` has
written the new pin and parameter list, and before `Open / update the bump PR`. The
Docker setup, `make test-env`, and the live target MUST run only when
`matrix.id == 'tensorfold'`. The bump job MUST be allowed to pull the test image
(`packages: read`). A failure of the live target MUST stop that row before the PR step.

WHEN the TensorFold bump has written its new pin
THEN the live archive proof runs, and only then does that row open the bump PR.

#### Scenario: tensorfold runs the live proof between the pin and the PR

- **Given** the `bump` job in `.github/workflows/engine-bump.yml`
- **When** its steps are read
- **Then** Docker setup, `make test-env`, and `make test-engine-bump-live` sit after
  `make engine-bump` and before the PR step, each gated on `matrix.id == 'tensorfold'`,
  and the job permission `packages` is `read`
- **Test:** `tests/test_engine_bump.py::test_unit_recipe_keeps_the_image_build_out`

### Requirement: hermetic bump tests stay on the unit suite

`make test-unit` MUST keep running `tests/test_engine_bump.py` and MUST keep
de-selecting the three live GitHub-release node ids. Those node ids stay on
`make test-engine-bump-live`.

WHEN the unit suite is selected
THEN the hermetic bump tests run and the three live node ids do not.

#### Scenario: the live node ids stay de-selected

- **Given** the unit-suite roster and `make test-engine-bump-live`
- **When** the aggregator selects the unit suite
- **Then** `tests/test_engine_bump.py` is selected, the image-build file is not, and
  `test_the_pinned_release_archive_unpacks_and_runs` is de-selected and named on the
  live target
- **Test:** `tests/test_engine_bump.py::test_unit_recipe_keeps_the_image_build_out`
