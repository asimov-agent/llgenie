# ci-security-images

## ADDED Requirements

### Requirement: the scanner images have their own pipeline, never a pull request

The scanner images are built and published by `.github/workflows/security-images.yml`, not by main
CI: a daily `schedule`, a `push` to `main` path-filtered to `containers/scanners/**` and
`scripts/scanner_image.py`, and a `workflow_dispatch`. The pipeline MUST NOT carry a `pull_request`
trigger, and `ci.yml` MUST NOT declare a scanner-job or run a scanner make target on a PR/merge.

WHEN a workflow owns the scanner images
THEN it runs on a schedule, a path-filtered push to main, and a manual dispatch — never a pull_request.

#### Scenario: security-images.yml never triggers on a pull request

- **Given** the repository's workflow files
- **When** `security-images.yml` is read
- **Then** its trigger surface is `schedule`/`workflow_dispatch` and a path-filtered `push`, with no `pull_request` key
- **Test:** `tests/test_scanner_images.py::test_security_images_yml_runs_never_on_a_pull_request`

#### Scenario: ci.yml builds and publishes no scanner image

- **Given** this repository's `ci.yml`
- **When** it is read for a scanner job or a scanner make target
- **Then** the `scanner-images` job is absent, and no `make ci-security-images` / `make ci-scanner-images` /
  `make publish-scanner-images` runs on a PR or merge
- **Test:** `tests/test_scanner_images.py::test_ci_yml_has_no_scanner_job`

### Requirement: publish only the tags GHCR is missing

`scanner_image.ensure` does ONE registry manifest lookup (`published`) per scanner and builds +
pushes both platforms only when that content-hash tag is absent, or when `FORCE` asks. A present tag
is a lookup and a log line, never a build. `published` is the same `buildx imagetools inspect` probe
`scripts/ci_images.py::published` uses. `FORCE` is a dispatch input passed as an env value, never a
workflow `if:`.

WHEN `ensure` runs for a scanner
THEN a tag already on GHCR is skipped (`present … (skipped)`), and an absent tag (or FORCE) is
published once with the digests ref.

#### Scenario: an already published tag is skipped

- **Given** a registry that already carries the content-hash tag on both platforms
- **When** `ensure` runs
- **Then** it prints `present … (skipped)` and runs no build or push (one manifest lookup only)
- **Test:** `tests/test_scanner_images.py::test_ensure_skips_a_published_ref`

#### Scenario: an absent tag is published exactly once

- **Given** a registry probe that exits non-zero (the tag does not exist)
- **When** `ensure` runs
- **Then** it prints `publishing` and runs exactly one `buildx build --platform linux/amd64,linux/arm64
  --push -t <ref>` named with the digests.json ref
- **Test:** `tests/test_scanner_images.py::test_ensure_publishes_an_absent_ref`

#### Scenario: FORCE republishes even a present tag

- **Given** a registry that already carries the tag on both platforms and `FORCE` set in the environment
- **When** `ensure` runs with the force input
- **Then** it publishes anyway (a `--push` runs, named the ref)
- **Test:** `tests/test_scanner_images.py::test_ensure_force_republishes_a_present_ref`

### Requirement: the scan obtains a missing image through the ONE builder

`security_scan.ensure_image` carries no `docker build` of its own. A pull that misses delegates to
`scanner_image.ensure` for that one scanner, so a missing image is obtained through the single
implementation, and the run is never silently skipped for a scanner that cannot be obtained.

WHEN a scan needs an image that is not yet published
THEN it delegates the build to `scanner_image.ensure`, and a scanner that cannot be obtained fails
the run loudly.

#### Scenario: a pull miss delegates the build to scanner_image.ensure

- **Given** a docker whose pull fails
- **When** `ensure_image` resolves the image
- **Then** it returns the digests ref, calls `scanner_image.ensure(scanner=tool)`, and hand-rolls no
  `docker build` of its own
- **Test:** `tests/test_scanner_images.py::test_ensure_image_has_single_build_path`
  and `tests/test_security_scan.py::test_a_pull_miss_delegates_the_build_to_scanner_image_ensure`

#### Scenario: a scanner that cannot be obtained is loud, never a silent skip

- **Given** a docker whose pull fails and a builder that cannot build the image either
- **When** `ensure_image` resolves the image
- **Then** it raises, naming the scanner
- **Test:** `tests/test_security_scan.py::test_a_build_failure_is_loud`
