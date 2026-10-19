# ci-engine-images

## ADDED Requirements

### Requirement: the install job waits for the images it is about to pull

When a CI run installs the engine images for a backend, it MUST first wait for
every image tag that `make install` would pull for that backend to appear in the
registry, and only then pull. The tags the gate resolves MUST be the tags
`install()` resolves for the same backend (same engine set, same variant
resolution, same tag computation). The gate MUST NOT build an image, MUST NOT
pull a different tag, and MUST NOT skip an engine it cannot find.

#### Scenario: a bump PR's install job waits for its own new tag
- **Given** a `pull_request` run whose engine-image job is still building and
  has not yet pushed the new pinned tag
- **When** the `install` job runs `make ci-install`, which runs
  `make ci-wait-engine-images ARCH=cpu` before `make ci-install-run`
- **Then** the gate polls the registry until that tag is published
- **And** `make install` pulls it instead of failing `not published`
- **Test:** `tests/test_ci_publish_order.py::test_install_job_waits_before_it_installs`

#### Scenario: the gate is a prerequisite, not a second job step
- **Given** the reusable pipeline's `install` job and the `ci-install` recipe
- **When** the job's `run:` steps are read
- **Then** the job runs exactly one `make ci-<job>` target, and the wait is inside
  that target's recipe
- **And** no `make ci-wait-engine-images` step sits beside `make ci-install`
- **Test:** `tests/test_ci_publish_order.py::test_the_install_job_runs_one_make_target`
  and `tests/test_ci_images.py::test_every_pipeline_job_runs_one_ci_make_target`

#### Scenario: the gate resolves exactly the tags install pulls
- **Given** the committed engine params of this repo and a backend
- **When** the gate resolves the tags to wait for
- **Then** they are exactly the tags `install()` would pull for that backend
- **And** no other tag is waited for
- **Test:** `tests/test_ci_publish_order.py::test_the_gate_waits_for_exactly_what_install_pulls`

#### Scenario: a tag that never appears fails loudly
- **Given** a backend whose image tag is not in the registry and never will be
- **When** the gate waits for it with its attempts exhausted
- **Then** the gate returns non-zero
- **And** it names every tag that is still missing
- **Test:** `tests/test_ci_publish_order.py::test_a_never_published_tag_fails_loudly`

#### Scenario: an already published image needs no wait
- **Given** a backend whose images `make install` pulls are already published
- **When** the gate waits for them
- **Then** it returns zero without consuming its retry budget
- **Test:** `tests/test_ci_publish_order.py::test_published_images_need_no_wait`

#### Scenario: the macOS install job is not gated
- **Given** the `ci-wait-engine-images` target and the OS-neutral `ci-install` recipe
- **When** either OS runs `make ci-install`
- **Then** `ci-install` runs the same targets on both OSes, with no Darwin branch
- **And** only the gate target branches on the OS, and its Darwin branch does no
  registry lookup
- **And** the gate target is defined after `HOST_OS := $(shell uname -s)`, because make
  evaluates `ifeq` while parsing, so an earlier conditional would see an empty `HOST_OS`
  and take the Linux branch on macOS too
- **Test:** `tests/test_ci_publish_order.py::test_macos_install_is_not_gated`
  and `tests/test_macos_install.py::test_macos_ci_does_not_run_docker_github_actions`

### Requirement: a same-repo PR run publishes the images it built

A `pull_request` run of a branch in this repository MUST publish every engine
image it builds and tests, one image per engine × backend variant, before any
later stage of that run pulls it. A run that cannot publish MUST fail loudly
rather than pass while its images were never published.

#### Scenario: a bump PR publishes its changed variants
- **Given** a bump PR that moves one engine's pin
- **When** its CI run builds that engine's CI variants
- **Then** each built and tested variant is pushed under its pinned tag
- **And** the run's own install job can pull that tag
- **Test:** `tests/test_engine_image_matrix.py::test_a_moved_pin_builds_only_that_engine`
  and `tests/test_ci_publish_order.py::test_install_job_waits_before_it_installs`
