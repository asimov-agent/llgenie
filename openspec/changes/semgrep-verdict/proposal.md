# semgrep-verdict — proposal

Issue: [#1554](https://github.com/asimov-agent/llgenie/issues/1554) (security admission-gate:
semgrep SAST findings never reach the verdict / issues / bumps).

## Why

The Semgrep SAST leg of the security pipeline runs and its report is uploaded, but its findings can
**never** gate the run, be filed as an issue, or drive a floor bump: `scripts/security_scan.py::findings()`
(policy #1554) reads `trivy.json` (vuln + secret) and `grype.json` but has **no `semgrep.json` reader
and no `("semgrep.json", …)` entry**. The report is produced (line 190-191) and uploaded as an
artifact, but never read. `make security-verdict`, `make security-issues` and `make security-bumps`
all read only `findings()`, so a green verdict means "no trivy/grype finding", never "no SAST finding"
— a side-by-side there is not even a "stale pin" to detect (the freshness gap #1284/#1375).

Measured at `main@504bda0a` with the pinned scanner images: a probe tree carrying SQL injection
(`sqlalchemy-execute-raw-query`), command injection (`subprocess-shell-true`) and unsafe pickle
(`avoid-pickle`) produced **4 semgrep findings, 2 at severity ERROR**, while `security_scan.py
verdict` on the same tree printed exactly one finding — the trivy certifi advisory. Semgrep severity
(`ERROR`/`WARNING`/`INFO`) is not in the policy's known set, so even the mapping would need the fix.

## What Changes

- **`scripts/security_scan.py`**: a `SEMGREP_SOURCE = "semgrep"` source and a
  `SEMGREP_SEVERITY = {ERROR → high, WARNING → medium, INFO → low}` map; a `_semgrep_findings`
  reader normalising `semgrep.json` `results[]` (id = `check_id`, package = `path:line`,
  current = matched region, fixed = `""`); a `("semgrep.json", _semgrep_findings)` entry in the
  `findings()` reader tuple so verdict / issues / bumps all see SAST findings.
- **SAST findings are always actionable** (like a committed secret, #1283): a semgrep finding has no
  `fixed` version — its remediation is editing the matched code — so `require_fix` must not keep it
  out of `blocking()` (verdict) or `issue_findings()` (tracker). `blocking()` and
  `security_issues.py` treat `SEMGREP_SOURCE` as always-actionable, exactly like `SECRET_SOURCE`.
- **`tests/test_security_scan.py` + `test_security_issues.py`**: a semgrep finding flows through
  `findings()` into a blocking verdict (no mocked scanner — real `semgrep.json` fixture in a reports
  dir, same shape as `test_a_committed_secret_flows_through_findings`); an ERROR blocks even with
  `require_fix` (mapped to `high`); a WARNING is recorded never blocking (mapped to `medium`); a
  semgrep finding becomes a `component:code` issue with `severity:high` and never `auto-fixable`.
- **`make check-security-scan`** must still refuse any `push`/`pull_request` trigger (#738) — the
  scan stays its own daily pipeline; this change only makes SAST output *visible*, it adds no gate.

## Out of scope

Rule-set pinning/freshness (#1284/#1375) and engine install-string pins (#1282) — owner-gated,
unchanged. This change only makes the already-produced SAST output reach the gate; it does not add a
`push`/`pull_request` trigger — the scan remains its own daily pipeline (#738).
