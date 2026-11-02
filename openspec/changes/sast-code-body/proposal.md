# sast-code-body — proposal

Issue: [#1560](https://github.com/asimov-agent/llgenie/issues/1560) (security SAST): semgrep
findings file issues whose body tells the reader to bump a nonexistent requirement.

## Why

`scripts/security_issues.py::body_for` renders the SAME dependency-flavoured template for every
finding, `component:code` included. A SAST finding that gates the daily scan files an issue whose body
tells the reader to do a package-bump action that cannot exist: a `component:code` finding lives in a
file, not a requirements pin, and its remediation is editing the matched source — never
"`tools/app.py:5` is pinned at `(no fixed version named)` or later in the compiled `requirements*.txt`".

The wrong remediation is how a SAST finding gets "closed" without the code being fixed — the gate stays
red, or the issue is closed with no code change while the scan keeps re-reporting. It also breaks the
reader's trust in `component:code` labelling: the label says "edit code", the body says "bump a pin".

## What Changes

- **`scripts/security_issues.py::body_for`**: branch on the finding's component. A `component:code`
  finding (a SAST or committed-secret finding — `source` not in a CVE scanner's vocabulary) renders
  the *edit-the-code* present-tense narrative — "the matched region in `tools/app.py:5` is the defect;
  fix it in source, commit, let the next scan confirm" — instead of the *bump-the-pin* template. A
  CVE-style finding (`component:python` / `component:container`) keeps the existing pin template. The
  branch keys on the same classification the verdict already uses: `component_of` maps
  `source not in ("trivy","grype")` to `component:code`, so `finding.component` is the branch.
- **Idempotency is presentation-invariant**: the marker (the idempotency key), advisory id, severity,
  component and run link are identical for both shapes — only the body prose changes.

## Out of scope

The marker/severity mapping itself (verified sound in the advisory) — this issue is prose shape only,
and only for `component:code`. No scanner pin, allowlist or severity set widens; no `push` /
`pull_request` trigger is added to the scan workflow (it stays its own daily pipeline, #738).
