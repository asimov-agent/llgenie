# Request Trivy's misconfig IaC scanner

## Why

Trivy's `misconfig` (IaC) vulnerability class never runs: `scripts/security_scan.py` invokes the
pinned trivy image with `--scanners vuln,secret`, so a Dockerfile / Compose / Terraform / GitHub
Actions hardening defect is invisible to every scan the daily gate runs — while the module docstring
and `docs/SCANNERS.md` both advertise misconfig coverage (issue #2234). The same `vuln,secret` →
`+misconfig` shape issue #1283 already closed for the `secret` class; `misconfig` is the one
advertised capability the runtime never requests.

## What changes

- `scripts/security_scan.py` extends the trivy invocation to `--scanners vuln,secret,misconfig`
  (JSON verdict run and SARIF upload run both), so the same digest-pinned trivy image also reports
  IaC drift. No new image, no new network: trivy 0.70.0-r5 ships the built-in misconfig checks.
- A `_trivy_misconfig_findings` reader normalises the `Results[].Misconfigurations[]` matches
  (Class `config`) into the shared finding shape with a distinct `trivy-misconfig` source, wired
  into `findings()` alongside the vuln and secret readers.
- A misconfiguration is ALWAYS actionable (its fix is editing the matched IaC, not awaiting a
  patched package version), so `blocking()` and `issue_findings()` treat `MISCONFIG_SOURCE` —
  like a committed secret / a SAST finding — as not suppressed by `require_fix`, while `fail_on`
  still gates the severity. `security_issues.py::component_of` already maps any non-(trivy,grype)
  source to `component:code`, so a misconfig issue is labelled a file rule.
- Tests prove the invocation carries all three scanners, the reader normalises a real misconfig
  shape (measured against the pinned image on a planted bad Dockerfile), a HIGH misconfig blocks
  even with `require_fix`, a MEDIUM is recorded / never blocks, and the finding flows through the
  shared `findings()` gate alongside a CVE. The dormant negative control is the `DS-0002`
  fixture: with `misconfig` removed from the flag set the same report yields no config result.
- `docs/SCANNERS.md` and the module docstring now describe exactly what runs.

## What does not change

No policy/`fail_on`/severity set, no allowlist, no `push:`/`pull_request:` trigger on the scan
pipeline (#738), no scanner image or digest change. The trivy image is already content-pinned
(`ghcr.io/asimov-agent/llgenie/trivy:0abec50ba0db`, exact package `trivy=0.70.0-r5`) and its
built-in misconfig rule set is that pin's — so the scanner cannot silently drift its checks
without a reviewed Dockerfile + digest change.

## Acceptance

- [x] The daily `security-scan` trivy invocation requests `misconfig` (`--scanners vuln,secret,misconfig`) in both the JSON and SARIF runs.
- [x] A planted bad Dockerfile (missing non-root `USER`, `DS-0002`) is reported at a named head sha by the same pinned trivy image with `misconfig` in the flag set, and produces no config result when `misconfig` is removed.
- [x] A HIGH misconfig is a first-class finding (blocks even with `require_fix`); a MEDIUM is recorded, never red; the policy still honours the no-PR-gate contract (#738).
- [x] `docs/SCANNERS.md` and the `security_scan.py` docstring match what actually runs.
