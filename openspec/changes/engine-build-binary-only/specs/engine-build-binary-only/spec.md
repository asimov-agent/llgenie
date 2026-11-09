# engine-build-binary-only

## ADDED Requirements

### Requirement: engine-build runs no serving step for any cell
The `engine-build` CI workflow SHALL NOT start or serve an inference container for
any engine x arch cell. The `serve-leg` (`make test-published-engine` serving the
image and answering "hi") and the `host-verify MATRIX` (`make test-engine-host`
parallel serve) steps SHALL NOT be present. The workflow's per-row gate SHALL be
build → binary verify → bind-proof → push → published-binary-leg → install-leg.
Dispatch inputs SHALL be exactly `engine`, `arch`, `push`, `force`.

#### Scenario: a build cell runs only the binary gate after publish
- **Given** a requested engine × arch cell
- **When** the workflow runs its per-row job
- **Then** it builds, verifies the binary with `-h`/`--version`, and on `push=true`
  publishes the image and verifies the BINARY of the just-published image
- **And** it never starts or waits on an inference server
- **Test:** `tests/test_engine_build_workflow.py` (workflow no longer contains the
  serve-leg/host-verify steps)

### Requirement: the CI binary probe is exactly -h and --version
Both paths in `scripts/engine_smoke.py` SHALL probe exactly the flags `-h` then
`--version`, ignoring `variant_flags`/`documented`/`binary_flags` extras as the
probe set. `TYPED_FLAGS` in `scripts/engine_image.py` MAY stay the full
`("--version","-h","--help","-V")` set the owner confirmed, but CI SHALL NOT probe
`--help` or `-V`.

#### Scenario: the smoke probe set is pinned to two flags
- **Given** an engine whose skill documents `--version --help -h -V`
- **When** either the image-build or the host/skill smoke path runs
- **Then** it probes exactly `-h` and `--version`, in that order, and nothing more
- **Test:** `tests/test_engine_skills.py`, `tests/test_published_gate.py` (probe set
  equality)

### Requirement: serving conformance is a host-only action
The serving conformance test SHALL NOT run in CI. `make test-engine-host
ENGINE=<id> ARCH=<arch> [MODEL=...]` and `make test-engine-serve ENGINE=<id> ARCH=<arch>`
SHALL still exist and be documented as HOST-only, run by the engine improver one
engine at a time. `make test-published-engine` SHALL verify only the binary
`-h`/`--version` of the as-published image, never start a server.

#### Scenario: the host serve commands remain and are documented host-only
- **Given** the Makefile and engine-build workflow at the PR head
- **When** the doc and workflow are inspected
- **Then** `test-engine-host` / `test-engine-serve` exist and carry a host-only note
- **And** `test-published-engine` has no `--serve` chat invocation
- **Test:** `tests/test_engine_build_workflow.py`, `tests/test_published_gate.py`
