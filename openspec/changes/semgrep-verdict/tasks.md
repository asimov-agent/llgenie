# Tasks

- [x] 1. `scripts/security_scan.py`: `SEMGREP_SOURCE = "semgrep"` + `SEMGREP_SEVERITY` map
  (`ERROR → high`, `WARNING → medium`, `INFO → low`)
- [x] 2. `scripts/security_scan.py`: `_semgrep_findings(report)` reader normalising `results[]`
  (id = check_id, package = path:line, current = matched region, fixed = `""`, source = semgrep)
- [x] 3. `scripts/security_scan.py`: `("semgrep.json", _semgrep_findings)` in the `findings()` reader
  tuple
- [x] 4. `scripts/security_scan.py`: `blocking()` treats `SEMGREP_SOURCE` as always actionable
  (same branch as `SECRET_SOURCE`) — a SAST finding's remediation is editing the code, never
  "await a patched version"
- [x] 5. `scripts/security_issues.py`: `issue_findings()` exempts `SEMGREP_SOURCE` from
  `require_fix` suppression (like `SECRET_SOURCE`); `check()` marker round-trip covers a semgrep
  example
- [x] 6. `tests/test_security_scan.py`: semgrep fixtures; `_semgrep_findings` normalisation test;
  a semgrep finding flows through `findings()` into a blocking verdict (no mocked scanner); an ERROR
  blocks even with `require_fix`; a WARNING is recorded never blocking
- [x] 7. `tests/test_security_issues.py`: a semgrep finding becomes a `component:code` issue with
  `severity:high`, no `auto-fixable`, despite no `fixed` version
- [x] 8. Verification: real `semgrep.json`-only reports dir → `python3 scripts/security_scan.py
  verdict --event schedule` exits non-zero naming the semgrep findings (the sabotage proof); the full
  security-pytest suite green; `make check-security-scan` refuses push/pull_request triggers
- [x] 9. `make openspec-validate NAME=semgrep-verdict` green and every task above ticked
