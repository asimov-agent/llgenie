# The trivy misconfig IaC class is now requested by the security-scan gate (issue #2234)

Issue: [#2234](https://github.com/asimov-agent/llgenie/issues/2234). Trivy's `misconfig` (IaC:
Dockerfile / Compose / Terraform / K8s / GitHub Actions) vulnerability class was never run: the
daily `security-scan` gate invoked the pinned trivy image with `--scanners vuln,secret`, so a
Dockerfile or workflow hardening defect was invisible to every scan — while the module docstring and
`docs/SCANNERS.md` both advertised misconfig coverage.

## What was verified

Measured against the pinned trivy image at base `da83db09`
(`ghcr.io/asimov-agent/llgenie/trivy:0abec50ba0db`, exact package `trivy=0.70.0-r5`, in
`containers/scanners/digests.json`): the image ships a working `misconfig` scanner, and a planted
bad Dockerfile (missing its non-root `USER` → `DS-0002`, HIGH) IS reported when the invocation
carries `--scanners vuln,secret,misconfig`, and yields no `config`-class result when `misconfig` is
removed from the flag set — the red/green negative control, proven on the real scanner, not asserted.

## What changed

- `scripts/security_scan.py`: the trivy invocation is now `--scanners vuln,secret,misconfig` in both
  the JSON verdict and the SARIF upload runs. The built-in misconfig rule set is part of the pinned
  version's own content (trivy 0.70.0-r5), so the existing content-hash image pin is the
  rule-set pin — the scanner cannot silently drift its checks without a reviewed Dockerfile/digest
  change.
- A `_trivy_misconfig_findings` reader normalises `Results[].Misconfigurations[]` matches (under a
  `config`-class result) into the shared finding shape with the distinct `trivy-misconfig`
  (`MISCONFIG_SOURCE`) source, wired into the same `findings()` gate as the vuln and secret readers.
- A misconfiguration is always actionable (its fix is editing the matched IaC, never awaiting a
  patched package version), so `blocking()` and `security_issues.py::issue_findings()` never
  suppress it via `require_fix` — exactly like a committed secret or a SAST finding — while
  `fail_on` still gates the severity and `component_of` labels it `component:code`.
- Tests cover the invocation carrying all three scanners, the reader normalising a real misconfig
  shape, a HIGH misconfig blocking even under `require_fix`, a MEDIUM being recorded / never red,
  and the finding flowing through the shared gate alongside a CVE.
- `docs/SCANNERS.md` and the `security_scan.py` module docstring now state exactly what runs.
- OpenSpec change `misconfig-trivy-iac-scan` records the requirement set.

## What does not change

No policy/`fail_on`/severity set, no allowlist, no `require_fix: false`, no `push:`/`pull_request:`
trigger on `security-scan.yml` (the #738 contract holds — a newly-seen misconfig finding files an
issue and may red the daily run, never a PR).
