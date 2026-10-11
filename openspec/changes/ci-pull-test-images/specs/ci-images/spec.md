## ADDED Requirements

### Requirement: CI test images are tagged by a hash of their inputs
`scripts/ci_images.py` MUST tag `llgenie/test` with a hash of `containers/test/Dockerfile`,
`tools/requirements.txt` and `tools/requirements-dev.txt`, and `llgenie/openspec` with a hash of
`openspec/Dockerfile`, as `<LLGENIE_REGISTRY>/llgenie/<name>:<hash>` (lowercase). The build
context MUST contain exactly those inputs.

WHEN an image's inputs are unchanged
THEN its tag is unchanged; WHEN any input changes, THEN its tag changes.

#### Scenario: the tag follows the image's inputs
Given  a repo copy with the test image's Dockerfile and both lockfiles,
When   the tag is computed, a lockfile line is changed and the tag is computed again,
Then   the same inputs give the same tag,
And    the changed lockfile gives a different tag, while the openspec image's tag stays the same.
- **Test:** `tests/test_ci_images.py::test_tag_follows_the_image_inputs`

#### Scenario: the published ref names the registry and the hash
Given  `LLGENIE_REGISTRY=ghcr.io/Asimov-Agent`,
When   the refs of both images are printed,
Then   they are `ghcr.io/asimov-agent/llgenie/test:<12 hex>` and `ghcr.io/asimov-agent/llgenie/openspec:<12 hex>`.
- **Test:** `tests/test_ci_images.py::test_ref_names_the_registry_and_the_hash`

### Requirement: CI publishes each CI image once per hash
`make publish-ci-images` MUST look the hash tag up on the registry and, only when it is
missing, build the image for linux/amd64 and linux/arm64 with a registry layer cache and push it.

WHEN the hash tag is already published
THEN nothing is built; WHEN it is missing, THEN a two-arch buildx build pushes it.

#### Scenario: an already published hash is not rebuilt
Given  a registry that already has the test image's hash tag,
When   `ci_images.py publish test` runs,
Then   it only looks the tag up and builds nothing.
- **Test:** `tests/test_ci_images.py::test_publish_skips_a_published_hash`

#### Scenario: a new hash is built for both arches and pushed
Given  a registry without the test image's hash tag,
When   `ci_images.py publish test` runs,
Then   one `buildx build --platform linux/amd64,linux/arm64 --push` runs with `--cache-from`/`--cache-to` on the registry,
And    its context holds the Dockerfile and both lockfiles.
- **Test:** `tests/test_ci_images.py::test_publish_builds_both_arches_and_pushes_a_new_hash`

### Requirement: CI jobs pull the CI images and never build them
`make test-image-pull` / `make openspec-image-pull` MUST pull the hash tag and tag it as
`llgenie/test:latest` / `llgenie/openspec:latest`, and MUST fail without building when the tag
is missing. No workflow job other than `ci-images` may build a CI image.

WHEN a CI job needs a CI image
THEN it pulls the published hash tag; WHEN the tag is missing, THEN the job fails.

#### Scenario: a missing tag fails the pull loudly
Given  a registry without the test image's hash tag,
When   `ci_images.py pull test` runs,
Then   it exits non-zero, names the missing ref and never builds.
- **Test:** `tests/test_ci_images.py::test_ci_pull_fails_loudly_and_never_builds`

#### Scenario: the pulled image gets the local name the make targets use
Given  a registry with the test image's hash tag,
When   `ci_images.py pull test` runs,
Then   the hash ref is pulled and tagged `llgenie/test:latest`.
- **Test:** `tests/test_ci_images.py::test_ci_pull_tags_the_local_name`

#### Scenario: no CI job builds a CI image
Given  every workflow in `.github/workflows`,
When   their `run:` steps are read,
Then   none runs `make test-image` or `make openspec-image`, only `ci-images` runs `make publish-ci-images`,
And    every job that pulls a CI image needs `ci-images`, directly or through its caller (`pipeline.yml`, `pipeline-macos.yml`, `published.yml`).
- **Test:** `tests/test_ci_images.py::test_no_ci_job_builds_a_ci_image`

### Requirement: local make test-image pulls the published image when it exists
`make test-image` / `make openspec-image` MUST pull the published image of the current hash and
MUST build it from the same Dockerfile only when that hash is not published.

WHEN the current hash is published
THEN it is pulled and not built; WHEN it is not, THEN it is built locally under the same local name.

#### Scenario: a published hash is pulled, not built
Given  a registry with the test image's hash tag,
When   `ci_images.py ensure test` runs,
Then   it pulls and tags `llgenie/test:latest` without a build.
- **Test:** `tests/test_ci_images.py::test_local_image_is_pulled_when_published`

#### Scenario: an unpublished hash is built locally
Given  a registry without the test image's hash tag (an edited lockfile),
When   `ci_images.py ensure test` runs,
Then   it builds `llgenie/test:latest` from the Dockerfile and both lockfiles and says why.
- **Test:** `tests/test_ci_images.py::test_local_image_is_built_when_not_published_yet`

### Requirement: macOS runs the pipeline's make targets in three Docker jobs
Every Linux pipeline job (`pipeline.yml`) MUST run exactly one `make ci-<job>` target.
`pipeline-macos.yml` MUST run the same targets as ordered steps of `checks` and `serve` that
run even after a failed step, plus `install`, so only 3 macOS jobs boot Docker. Neither file
may hold a job for the other OS.

WHEN the pipeline runs on macOS
THEN three jobs boot Docker and together run exactly the make targets the Linux jobs run.

#### Scenario: the macOS jobs cover exactly the Linux jobs
Given  `pipeline.yml` and `pipeline-macos.yml`,
When   the make targets of their jobs are collected,
Then   both sets are equal,
And    no job of either file has an `if:`,
And    every macOS step after the first image pull runs `if: ${{ !cancelled() }}` or `always()`,
And    exactly three macOS jobs use the Docker setup action.
- **Test:** `tests/test_ci_images.py::test_macos_runs_the_linux_targets_as_steps_of_three_jobs`

#### Scenario: every pipeline job is one make target
Given  `pipeline.yml` and the Makefile,
When   each job's steps are read,
Then   it runs exactly one `make ci-<job>`, which exists in the Makefile,
And    `ci-install` runs `make test-install-ci`.
- **Test:** `tests/test_ci_images.py::test_every_pipeline_job_runs_one_ci_make_target`

### Requirement: no CI job or step is skipped
A job or step in `ci.yml`, `pipeline.yml` or `published.yml` MUST NOT carry a condition that
skips it in a push run that has engines to build. A job may only wait for its needs
(`!cancelled()`, and the push event). `matrix` is not a legal name in a job-level `if:`, and an
empty include list fails the workflow before any job `if:` runs, so a PR that changes no engine
params emits one `engine: none` row and every step of `engine-image` / `engine-published-test`
skips `matrix.engine == 'none'` (issue #107). `linux-published` runs on a `pull_request` too, so
the required `install-published-*` check names report (a skipped `uses:` job reports nothing,
and the merge then waits forever). A step may only use `!cancelled()`, `always()`,
`runner.os == 'Linux'` / `runner.os == 'macOS'`, or `matrix.engine != 'none'`. OS- and
matrix-specific work is decided inside make (`make ci-free-disk`, `make test-engine-stage
TEST=serve|detect`).

WHEN a branch is pushed and the engine matrix is non-empty
THEN every job and every step of the run executes; none shows as skipped.

#### Scenario: no workflow condition skips a job or a step
Given  every CI workflow,
When   every job-level and step-level `if:` is collected,
Then   jobs only wait for their needs, steps only `!cancelled()`, `always()`, a runner.os check, or the `matrix.engine != 'none'` placeholder skip,
And    the free-disk and post-build-test decisions are the make targets `ci-free-disk` and `test-engine-stage`.
- **Test:** `tests/test_ci_images.py::test_no_ci_step_or_job_is_skipped`

### Requirement: the live pipeline publishes once and every job pulls
On a push run, CI MUST publish both CI images (or find them published) in `ci-images`, and every
Linux and macOS job MUST pull them instead of building.

WHEN a branch is pushed
THEN `ci-images` publishes the missing hashes, and every job's log shows a pull, not a build.

#### Scenario: the CI images exist on GHCR and are pulled
Given  a push run of this branch,
When   `ci-images` and the pipeline jobs finish,
Then   `ghcr.io/<owner>/llgenie/test:<hash>` and `.../openspec:<hash>` exist for amd64 and arm64,
And    no job runs a test-image build.
- **Test:** CI job `ci-images` -> `make publish-ci-images`; every pipeline job -> `make test-image-pull`
