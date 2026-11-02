# semgrep-verdict — spec delta

Capability: `security-scan`
Issue: [#1554](https://github.com/asimov-agent/llgenie/issues/1554)

## MODIFIED Requirements

### Requirement: the scan's own findings reach the verdict, the tracker and the bumps

`scripts/security_scan.py::findings()` SHALL read every report the pipeline produces in one normalised
shape — `trivy.json` (vulnerabilities), `trivy.json` (committed secrets), `grype.json` and now
`semgrep.json` — so a single reader feeds `verdict()`, `security_issues.py::issue_findings()` and
`security_bumps.py::floors`. A Semgrep SAST finding SHALL be normalised with id = `check_id`,
package = `path:line`, current = the matched source region, fixed = `""`, source = `semgrep`, and a
severity mapped from Semgrep's vocabulary (`ERROR → high`, `WARNING → medium`, `INFO → low`) into the
policy's gated set, so `verdict()` counts SAST findings against `fail_on`.

WHEN a `semgrep.json` report exists in the reports directory,
THEN every rule hit in its `results[]` is a finding in the shared shape with the gated severity.

#### Scenario: a semgrep finding flows through findings() into a blocking verdict
Given a reports directory holding only a `semgrep.json` whose results include one `ERROR` hit,
When   `findings()` is read and `verdict(mode="full")` is applied under the shipped policy
       (`fail_on` includes `high`),
Then   the finding is present (source `semgrep`, severity `high`) and is in the blocking set, so the
       verdict exits non-zero and names it.
- **Test:** `tests/test_security_scan.py::test_a_semgrep_finding_flows_through_findings`,
  `tests/test_security_scan.py::test_an_error_semgrep_finding_blocks_even_with_require_fix`; sabotage
  proof: `SECURITY_REPORTS=<dir-with-only-semgrep.json> python3 scripts/security_scan.py verdict
  --event schedule` exits 1.

#### Scenario: a SAST finding is always actionable despite no fixed version
Given a `semgrep.json` result at the gated severity (mapped to `high`) and the shipped `require_fix`
policy,
When   `blocking()` and `issue_findings()` run,
Then   the finding is NOT suppressed for having no `fixed` version — editing the matched code is the
       remediation, exactly like a committed secret — and it becomes a `component:code` issue with
       `severity:high` and never `auto-fixable`.
- **Test:** `tests/test_security_scan.py::test_an_error_semgrep_finding_blocks_even_with_require_fix`,
  `tests/test_security_issues.py::test_a_semgrep_sast_finding_becomes_an_issue_despite_no_fix`

#### Scenario: a below-fail_on SAST finding is recorded, never a red
Given a `semgrep.json` result at `WARNING` (mapped to `medium`),
When   `blocking(mode="full", mode="pr")` runs under the shipped policy,
Then   it is recorded (present in `findings()`) but never blocking, and the report-only PR mode is
       empty too.
- **Test:** `tests/test_security_scan.py::test_a_semgrep_warning_is_recorded_never_blocking`

## UNCHANGED Requirements

### Requirement: the scan is its own daily pipeline, never a PR gate

`make check-security-scan` SHALL continue to refuse any `push:` / `pull_request:` trigger in
`.github/workflows/security-scan.yml` and any policy that would gate such an event — the scan runs on
`schedule` / `workflow_dispatch` only, and a pre-existing advisory or SAST finding must never red a
pull request (#738). This change adds no gate trigger; it only makes already-produced SAST output
visible to the existing one.

WHEN the workflow's `on:` block or the policy is read by `check`,
THEN a `push` or `pull_request` trigger is refused (the check exits non-zero).

#### Scenario: the check still refuses a push / pull_request trigger
Given the shipped workflow and policy,
When   `make check-security-scan` runs,
Then   it reports the scan triggers only on `schedule, workflow_dispatch` and exits zero — no new
       gate-weakness regression.
- **Test:** `tests/test_security_scan.py::test_the_workflow_uses_the_digests_and_a_manual_form` (no `pull_request:`
  / `push:` in the workflow text), `tests/test_security_scan.py::test_check_refuses_a_policy_that_gates_a_push`
