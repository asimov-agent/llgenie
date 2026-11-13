## ADDED Requirements

### Requirement: The executed scanner image is verified against a recorded digest

`containers/scanners/digests.json` MUST record, per scanner, the manifest digest
(`image_digest`, `sha256:<64 hex>`) of the published image its content-hash tag serves — a content
tag is re-pushable and a re-build resolves whatever the package repository publishes that day, so
the tag alone does not pin what a scan actually runs. A scan invocation that pulls the pinned ref
MUST compare the registry manifest digest against the recorded one and exit non-zero naming BOTH
digests on a mismatch; every scan run MUST print the digest of the image it executed. A locally
built deferral image (issue #2518, unpublished tag) MUST print its built digest and state that the
registry pin cannot be registry-verified.

#### Scenario: every scanner ref carries a digest

Given this repository,
When   `make check-security-scan` and `make check-scanner-images` run,
Then   each exits 0, and every scanner entry in `containers/scanners/digests.json` carries an
       `image_digest` matching `sha256:<64 hex>`.

- **Test:** `tests/test_security_scan.py::test_every_scanner_ref_carries_an_image_digest`

#### Scenario: a moved image fails the scan naming both digests

Given a scanner whose recorded `image_digest` differs from the manifest digest the registry serves
for its pinned tag,
When   a scan invocation resolves that pinned ref,
Then   it exits non-zero naming the recorded digest and the actual digest.

- **Test:** `tests/test_security_scan.py::test_a_pinned_digest_mismatch_exits_naming_both_digests`
  (negative control: a scan on head with a deliberately wrong recorded digest exits 3 naming both)

#### Scenario: a scan run names the executed digest

Given a scan run of a pinned scanner on the pull path,
When   the run's output is read,
Then   it names the executed image's manifest digest beside the ref.

- **Test:** `tests/test_security_scan.py::test_a_scan_run_names_the_executed_image_digest`
  (proof in CI: the security-scan job log of this lane's run)

## MODIFIED Requirements

### Requirement: The published tag names one build of one Dockerfile

`containers/scanners/digests.json` MUST carry, per scanner, the pinned version, a tag equal to
the Dockerfile's content hash, and the published image's manifest digest as `image_digest`.
`make scanner-digests` MUST regenerate the file from the Dockerfiles and carry each entry's
`image_digest` forward when its tag is unchanged; `make pin-scanner-image-digests` MUST fill
`image_digest` from the published registry manifest. The gate MUST fail when the file is stale or
when a scanner entry lacks `image_digest`.

#### Scenario: write carries the digest forward

Given a `digests.json` whose entry keeps its content-hash tag,
When   `scanner_image.py write` rewrites the file,
Then   the entry keeps its recorded `image_digest`.

- **Test:** `tests/test_scanner_images.py::test_write_carries_image_digest_forward`

#### Scenario: a missing digest is a gate failure

Given a scanner entry without `image_digest`,
When   `scanner_image.py check all` runs,
Then   it exits non-zero naming the scanner and the missing field.

- **Test:** `tests/test_scanner_images.py::test_an_entry_without_an_image_digest_fails`
