# sast-code-body — spec delta

Capability: `security-scan`
Issue: [#1560](https://github.com/asimov-agent/llgenie/issues/1560)

## MODIFIED Requirements

### Requirement: the issue body's remediation matches the finding's component

`scripts/security_issues.py::body_for` SHALL render the remediation narrative that matches the
finding's component: a `component:code` finding (a SAST or committed-secret finding — `source` not in
a CVE scanner's vocabulary) renders the *edit-the-code* present-tense narrative — the matched region
is the defect, fix it in source, commit, let the next scan confirm — and SHALL NOT tell the reader to
bump a pin in `requirements*.txt`; a CVE-style finding (`component:python` / `component:container`)
keeps the existing *bump-the-pin* template unchanged.

WHEN a `component:code` finding is rendered,
THEN the body's `## How we fix it` and `## Acceptance criteria` tell the reader to edit the matched
source and do not mention the `requirements*.txt` pin path.

#### Scenario: a SAST body tells the reader to edit the code, not bump a pin
Given a semgrep finding (id = a check id, package = `tools/app.py:5`, empty `fixed`,
`component:code`),
When   `body_for` renders its issue body,
Then   the rendered body carries the code-remediation wording (edit the matched source, let the next
       scan confirm) and does NOT mention the generated `requirements*.txt` pin path, and the marker
       round-trips through `MARKER_RE` unchanged.
- **Test:** `tests/test_security_issues.py::test_an_sast_body_tells_the_reader_to_edit_the_code`

#### Scenario: a CVE body still tells the reader to bump the pin
Given a trivy/grype finding (`component:python`, a fixed version named),
When   `body_for` renders its issue body,
Then   the rendered body still carries the pin/`requirements*` wording, unchanged.
- **Test:** `tests/test_security_issues.py::test_the_body_states_advisory_package_versions_and_action`
  (CVE case keeps `requirements*.txt` wording)

## UNCHANGED Requirements

### Requirement: the scan is its own daily pipeline, never a PR gate

`make check-security-scan` SHALL continue to refuse any `push:` / `pull_request:` trigger in
`.github/workflows/security-scan.yml` — the scan runs on `schedule` / `workflow_dispatch` only, and a
pre-existing advisory or SAST finding must never red a pull request (#738). This change adds no gate.

### Requirement: the marker is the idempotency key

The body marker `<!-- security-finding: source:advisory:package -->` stays the first line and the
dedupe key for both body shapes, so a re-scan updates the same issue instead of opening a duplicate.
