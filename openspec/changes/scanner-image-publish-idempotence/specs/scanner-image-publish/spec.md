# scanner-image-publish

## ADDED Requirements

### Requirement: publishing an already-published content-hash tag is a no-op, and a publish failure names its streams

`scripts/scanner_image.py::publish` MUST probe the registry before running the multi-arch
`buildx build --push`: it runs `docker buildx imagetools inspect <ref>` through `scripts/proc.py`'s
`run_ok` policy (a tag the registry does not carry is a non-zero exit, never an exception). When the
published manifest list already carries every platform in `PLATFORMS`, `publish` MUST skip the push and
print a line naming the ref. Otherwise it MUST run the push unchanged. When a build or publish command
exits non-zero, the leg MUST print the command, its exit code, and a bounded tail of its captured
stdout+stderr — it MUST NOT discard the captured streams.

#### Scenario: an immutable tag already on the registry is not re-pushed

- **Given** the registry already carries `<registry>/llgenie/semgrep:<content-hash>` with
  `linux/amd64` and `linux/arm64` manifests (measured predecessor: run `42751641578`, job
  `129620581092`, published `ghcr.io/asimov-agent/llgenie/semgrep:5954e2aad609`)
- **When** `make ci-scanner-images` runs `publish("semgrep")` on a later main push
- **Then** the leg prints a skip line naming the ref, does NOT run `buildx build ... --push`,
  and returns 0
- **Test:** `tests/test_scanner_images.py` — faked registry probe listing both platforms asserts the
  skip line and the absence of any `--push` call

#### Scenario: a tag missing a required platform still publishes (negative control)

- **Given** the registry carries the tag but the manifest list lists only `linux/amd64`
- **When** `publish` runs with `PLATFORMS = linux/amd64,linux/arm64`
- **Then** the multi-arch `buildx build --platform linux/amd64,linux/arm64 --push` command runs
- **Test:** `tests/test_scanner_images.py` — faked probe with one platform asserts the recorded
  `--push` command

#### Scenario: a tag absent from the registry publishes as today

- **Given** the registry probe exits non-zero (the tag does not exist)
- **When** `publish` runs
- **Then** the probe's failure is NOT an exception or a leg failure, and the `--push` command runs
- **Test:** `tests/test_scanner_images.py` — faked probe rc=1 asserts the recorded `--push` command

#### Scenario: a failed publish prints the captured streams (issue #2452 criterion 4)

- **Given** a publish whose `buildx build --push` exits non-zero with a buildkit error in its stderr
- **When** `publish` handles the failure
- **Then** the printed output names the scanner, the command's exit code, and lines from the captured
  stdout/stderr, and the leg exits non-zero
- **Test:** `tests/test_scanner_images.py` — faked push rc=1 with a sentinel error line; the
  assertion reads the printed output for the sentinel and the exit code
