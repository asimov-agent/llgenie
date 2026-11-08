# trivy-misconfig-iac-scan

## ADDED Requirements

### Requirement: the trivy scan requests the misconfig IaC scanner

The daily `security-scan` trivy invocation MUST request Trivy's `misconfig` scanner for IaC
(Dockerfile / Compose / Terraform / K8s / GitHub Actions) alongside the existing `vuln` and
`secret` classes — `--scanners vuln,secret,misconfig` — in BOTH the JSON verdict run and the
SARIF upload run, so a Dockerfile / workflow hardening defect is a first-class finding and not
invisible to every scan (issue #2234).

WHEN the trivy scan runs
THEN the pinned trivy image is invoked with `--scanners vuln,secret,misconfig` in every format
run, so an IaC drift is reported by the same content-pinned image that already reports CVEs and
committed secrets.

#### Scenario: the invocation carries all three scanners

- **Given** the pinned trivy image (content-addressed by digest, exact package `trivy=0.70.0-r5`)
- **When** `make security-scan TOOL=trivy` runs
- **Then** both the JSON and SARIF runs pass `--scanners vuln,secret,misconfig`
- **Test:** `tests/test_security_scan.py::test_trivy_runs_all_three_scanners`

### Requirement: a misconfig finding is a first-class, always-actionable finding

A Trivy `misconfig`-class match (a `Results[].Misconfigurations[]` row under a result whose
`Class` is `config`) MUST be normalised into the shared finding shape with the distinct source
`trivy-misconfig`, MUST flow through the same `findings()` gate as the vuln and secret readers,
and MUST NOT be suppressed by `require_fix` — its remediation is editing the matched IaC, never
awaiting a patched package version — while `fail_on` still gates the severity and
`component_of` labels it `component:code`.

WHEN a misconfig finding is present in a trivy report with a `fail_on` severity
THEN it blocks a full-mode run even with `require_fix` on (like a committed secret / a SAST
finding), and a sub-`fail_on` severity is recorded, never a red.

#### Scenario: a HIGH misconfig blocks even under `require_fix`

- **Given** a trivy report with one HIGH misconfiguration (no package, no fixed version)
- **When** the full policy is applied
- **Then** it blocks, including under `require_fix: true`
- **Test:** `tests/test_security_scan.py::test_a_critical_misconfig_blocks_even_with_require_fix`

#### Scenario: a MEDIUM misconfig is recorded, never a red

- **Given** a trivy report with one MEDIUM misconfiguration
- **When** the full or report-only policy is applied
- **Then** it is not blocking
- **Test:** `tests/test_security_scan.py::test_a_medium_misconfig_is_recorded_never_blocking`

#### Scenario: the misconfig reader is wired into shared findings

- **Given** a trivy report carrying both a CVE advisory and a misconfiguration
- **When** `findings()` reads the report
- **Then** both the advisory and the misconfiguration are present in the shared shape
- **Test:** `tests/test_security_scan.py::test_a_misconfig_flows_through_findings`

### Requirement: the negative control — a planted bad Dockerfile is found with, missed without

The scan-coverage claim MUST be proven by the dormant control the tests encode: a deliberately
bad Dockerfile (missing its non-root `USER` → `DS-0002`) is reported by the new class when
`misconfig` is in the flag set, and yields no config result when it is not — measured on the
actual pinned trivy image, not asserted.

WHEN the planted bad Dockerfile is scanned with `--scanners vuln,secret,misconfig`
THEN it is reported (a HIGH `DS-0002`), and when the same file is scanned with `misconfig`
removed from the flag set THEN there is no `config`-class result.

#### Scenario: the planted bad Dockerfile is found with, missed without the flag

- **Given** a planted bad Dockerfile missing its non-root `USER` (the `DS-0002` shape)
- **And** the pinned trivy image of `0.70.0-r5`
- **When** the file is scanned with `--scanners vuln,secret,misconfig`
- **Then** a HIGH `DS-0002` misconfiguration is reported
- **And** when the same file is scanned with the `misconfig` flag removed from the set
- **Then** there is no `config`-class result
- **Test:** `tests/test_security_scan.py::test_trivy_runs_all_three_scanners` (invocation) and the measured live control against the pinned image
