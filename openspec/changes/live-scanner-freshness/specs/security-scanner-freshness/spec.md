## ADDED Requirements

### Requirement: The scanner freshness comparison SHALL judge pins against the live Wolfi package index

The security lane SHALL provide `make scanner-freshness`, which resolves the newest published Wolfi
x86_64 build for every pinned scanner package (`trivy`, `semgrep`, `grype`) and for the SBOM tool
(`syft`, whose pin is the `ARG SYFT_VERSION=` default in `containers/scanners/grype/Dockerfile`) by
parsing a Wolfi APKINDEX — fetched from `https://packages.wolfi.dev/os/x86_64/APKINDEX.tar.gz`, or
read from a local snapshot named by `WOLFI_APKINDEX` — and SHALL exit non-zero, naming for each
stale pin the package, the pinned version, and the live newest version, when any pin names anything
other than the newest published build.

#### Scenario: A pin lags the live index

- **WHEN** a pinned scanner version resolves in the index but is not the newest published build
- **THEN** `scanner-freshness` exits non-zero and its report names the package, the pinned version, and the live newest version

#### Scenario: Every pin is the live newest

- **WHEN** every pinned scanner version equals the newest build published in the index
- **THEN** `scanner-freshness` exits 0 and prints the index snapshot it measured against

#### Scenario: A pinned package is absent from the index

- **WHEN** a pinned scanner package has no entry in the index
- **THEN** `scanner-freshness` exits non-zero naming the package — an unresolvable pin is never a silent pass

#### Scenario: The comparison is hermetic under tests

- **WHEN** `WOLFI_APKINDEX` names a local APKINDEX snapshot
- **THEN** the step measures against that snapshot without network, so CI proves the behaviour deterministically

### Requirement: The offline `check-security-scan` gate SHALL remain network-free

`make check-security-scan` SHALL keep comparing `digests.json` against `SCANNER_BASELINE` with no
network call; the live comparison SHALL be its own explicit target so running it is a lane wiring
decision, not an accident inside an offline gate.

#### Scenario: check stays hermetic

- **WHEN** `make check-security-scan` runs with no network access
- **THEN** it completes with its existing verdict, and `scanner-freshness` remains separately invokable
