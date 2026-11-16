## MODIFIED Requirements

### Requirement: Pinned scanner image verification
The scan lane (`security-scan.yml` and `make security-scan-all`) runs each scanner
from the image pinned in `containers/scanners/digests.json`. Before executing a
pinned image, `verify_pinned_digest` proves the registry serves the recorded index
digest for the pinned ref, AND that the id the local daemon reports for that ref is
one of the identities the pinned index legitimately produces:

- the recorded index digest,
- the manifest digest of each child the pinned index names,
- the **config-blob digest** of each child manifest the pinned index names (a classic
  (non-containerd) Docker daemon reports a pulled image's id as its config digest;
  measured 2026-11-15/16: `grype:a607057cfd07` index `sha256:12ef938b…`, amd64 child
  `sha256:ccff82ef…`, child config `sha256:c585d524…`, which is the id the
  `ubuntu-latest` runner daemon reports).

A ref whose registry index no longer matches the recorded pin (a moved tag), or a
local id that belongs to no manifest or config named by the pinned index, still
exits non-zero naming both digests.

#### Scenario: runner-daemon config digest is accepted

- **WHEN** the registry serves the pinned index and the daemon reports the config
  digest of a child manifest of that index (the measured `ubuntu-latest` case)
- **THEN** `verify_pinned_digest` passes and the scan proceeds with that image

#### Scenario: stale local copy is refused

- **WHEN** the registry serves the pinned index but the daemon reports an id that is
  none of the index digest, child manifest digests, or child config digests
- **THEN** the scan exits non-zero naming the local id and the recorded pin

#### Scenario: moved tag is refused

- **WHEN** the registry serves an index digest other than the recorded pin
- **THEN** the scan exits non-zero naming the served index and the recorded pin
