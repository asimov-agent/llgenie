# Task 1: request the misconfig class in the trivy invocation

- [x] Extend `scripts/security_scan.py`'s trivy invocation from `--scanners vuln,secret` to `--scanners vuln,secret,misconfig` in both the JSON and SARIF runs.
- [x] Update the trivy scan comment and module docstring to state the misconfig class runs (reconciling both against `docs/SCANNERS.md`).

# Task 2: normalise and gate misconfig findings

- [x] Add `MISCONFIG_SOURCE = "trivy-misconfig"` and a `_trivy_misconfig_findings` reader for `Results[].Misconfigurations[]` under a `config`-class result, wired into `findings()` with the vuln and secret readers.
- [x] Treat `MISCONFIG_SOURCE` as always-actionable in `security_scan.py::blocking()` and `security_issues.py::issue_findings()` — never suppressed by `require_fix`, still gated by `fail_on` — and confirm `component_of` labels it `component:code`.

# Task 3: prove the red/green pair

- [x] Unit tests: a HIGH misconfig normalises and blocks even with `require_fix`; a MEDIUM is recorded / never red; the finding flows through `findings()` alongside a CVE.
- [x] Live negative control (measured, not asserted): a planted bad Dockerfile (no non-root `USER` → `DS-0002`) is found by `--scanners vuln,secret,misconfig` on the pinned trivy image, and produces no config result when `misconfig` is removed.

# Task 4: gates green

- [x] `tests/test_security_scan.py` and `tests/test_security_issues.py` pass in the test image.
- [x] `python3 scripts/security_scan.py check`, `make check-scanner-images`, `make lint` green; `make bot-preflight` names the base sha.
