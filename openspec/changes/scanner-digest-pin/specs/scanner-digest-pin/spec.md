# scanner-digest-pin

## ADDED Requirements

### Requirement: every scanner ref carries a recorded image digest, and a scan refuses to run an image that differs from it

`containers/scanners/digests.json` MUST record an immutable `digest` (the index digest of the image)
beside every scanner ref. `scripts/security_scan.py` MUST, before running a scanner, resolve the image
it would execute and compare its digest with the recorded one; a mismatch MUST exit non-zero naming
BOTH digests, and a missing or unparsable recorded digest MUST exit non-zero. Every scan run's output
MUST name the digest of the image it executed. `scripts/scanner_image.py::write` (`make
scanner-digests`) MUST record the digest alongside `version`/`tag`/`ref`.

#### Scenario: an image whose digest differs from the recorded one is refused

- **Given** a scanner ref whose recorded digest is `sha256:<expected>` and an image the scan resolves
  whose digest is `sha256:<actual>` where `<actual> != <expected>`
- **When** `security_scan` is about to run that scanner
- **Then** it exits non-zero and its output names both `<expected>` and `<actual>`
- **Test:** `tests/test_security_scan.py` — a faked inspect returning a differing digest asserts a
  non-zero refusal naming both digests

#### Scenario: a matching image runs and its output names the executed digest

- **Given** a scanner ref whose recorded digest equals the digest of the image the scan resolves
- **When** the scan runs the scanner
- **Then** it proceeds and its output names the matching digest
- **Test:** `tests/test_security_scan.py` — a matching inspect asserts the run proceeds and the
  recorded digest appears in the output

#### Scenario: digests.json regenerates with its digest, per scanner

- **Given** a scanner Dockerfile and `make scanner-digests`
- **When** `scanner_image.write` rewrites `digests.json`
- **Then** the per-scanner entry carries `version`, `tag`, `ref` and a `digest` field
- **Test:** `tests/test_scanner_images.py` — after `write()` the entry asserts a `digest` key exists

#### Scenario: the real tree's digests are sane and consistent

- **Given** this repository's `containers/scanners/digests.json`
- **When** `make check-security-scan` runs
- **Then** it passes: every scanner ref carries a `ref`, `tag`, `version` and a `digest`
- **Test:** `tests/test_security_scan.py::test_the_policy_and_digests_are_sane` and
  `tests/test_security_scan.py`'s digest-field check (the `check()` reds a missing `digest`)
