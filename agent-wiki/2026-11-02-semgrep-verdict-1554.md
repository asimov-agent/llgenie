# LLGenie Security Officer: semgrep SAST findings reach the verdict / issues / bumps

Implements issue #1554 (ready-for-review PR, never merged — CI lands it). The Semgrep SAST leg of
the security pipeline ran and uploaded its report, but its findings could **never** gate the run, be
filed as an issue, or drive a floor bump: the ONLY reader the verdict, issues and bumps consume,
`scripts/security_scan.py::findings()`, read `trivy.json` (vuln + secret) and `grype.json` but had
**no `("semgrep.json", …)` entry**. So `semgrep.json` (produced at line 190-191, uploaded as an
artifact) was structurally invisible — a green verdict meant "no trivy/grype finding", never "no SAST
finding".

## What changed (measured on this worktree)

- `scripts/security_scan.py` — added `SEMGREP_SOURCE = "semgrep"` and
  `SEMGREP_SEVERITY = {ERROR → high, WARNING → medium, INFO → low}` (Semgrep's vocabulary is not in
  the policy's known set). Added `_semgrep_findings()`: a `results[]` entry becomes the shared
  finding shape (`id` = `check_id`, `package` = `path:line`, `current` = the matched region
  `extra.lines`, `fixed` = `""`). `findings()` reader tuple now includes
  `("semgrep.json", _semgrep_findings)`.
- SAST findings are **always actionable** (like committed secrets, #1283): a semgrep finding has no
  `fixed` version, but its remediation is editing the matched code, never "await a patched version".
  `blocking()` and `scripts/security_issues.py::issue_findings()` treat `SEMGREP_SOURCE` the same way
  they already treat `SECRET_SOURCE`, so `require_fix` must not suppress them while `fail_on` still
  gates.
- `scripts/security_issues.py` — `issue_findings()` no longer lets `require_fix` keep a SAST finding
  off the tracker; it becomes a `component:code` issue with `severity:high` and never
  `auto-fixable` (a bump cannot fix code). `check()`'s marker round-trip now includes a semgrep
  example (`semgrep:<check_id>:<path>:<line>`).
- Tests: `tests/test_security_scan.py` (+6) and `tests/test_security_issues.py` (+1) prove the
  normalisation, the flow through `findings()` into a blocking verdict, the ERROR-blocks and
  WARNING-recorded cases, and the issue path. No scanner is mocked — real `semgrep.json` fixtures in
  a temp reports dir, the same shape as the #1283 secret test.

## Verification (measured, not asserted)

- Sabotage proof (no mocked scanner): `SECURITY_REPORTS=<dir-with-ONLY-semgrep.json> python3
  scripts/security_scan.py verdict --event schedule` → `[security-scan] FAIL (event=schedule,
  mode=full): 2 finding(s) at ['critical', 'high']` naming both ERROR-semgrep findings (mapped to
  `high`, in `fail_on`); previously the same tree printed **0 findings**. `security_issues.py plan`
  over the probe lists a `component:code` `severity:high` issue.
- Gates: `make check-security-scan` RC=0 (still refuses `push`/`pull_request` — the workflow
  triggers only on `schedule, workflow_dispatch`, so the scan stays its own daily pipeline #738);
  `make check-security-issues` RC=0; `make check-security-bumps` RC=0.
- Security pytest suite (`test_security_scan`, `test_security_issues`, `test_security_bot`,
  `test_issue_body`, `test_check_issue_body`): **70 passed**. `make openspec-validate
  NAME=semgrep-verdict` green.

This change never weakens the security gate: no `push`/`pull_request` trigger is added, no
allowlist/severity set is widened, and none of the owner-gated items (rule-set pinning/freshness
#1284/#1375, engine install-string pins #1282) are touched.
