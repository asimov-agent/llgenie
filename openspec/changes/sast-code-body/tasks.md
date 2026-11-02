# Tasks

- [x] 1. `scripts/security_issues.py::body_for`: branch on `finding.component == "component:code"` —
  render the *edit-the-code* present-tense narrative for SAST/secret findings, keep the pin template
  for CVE findings
- [x] 2. Idempotency invariant: marker, advisory id, severity, component and run link are identical in
  both body shapes (only the prose differs); the marker round-trips through `MARKER_RE`
- [x] 3. `tests/test_security_issues.py`: a rendered SAST body (`source=semgrep`,
  `component=component:code`, empty `fixed`, `package=tools/app.py:5`) carries the code-remediation
  wording and NOT the `requirements*.txt` pin wording; the CVE body (`source=trivy`) still carries the
  pin wording; the marker round-trips
- [x] 4. Re-run the #1557 reader chain: `make check-security-scan`, `make security-issues-plan` over a
  SAST-only reports dir, and the security pytest suite green
- [x] 5. `make openspec-validate NAME=sast-code-body` green and every task above ticked
