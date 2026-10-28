"""Findings become tagged issues, idempotently (issue #716).

The tracker is an external system, so the test gives `gh` a real executable that records its
arguments (`tests/fixtures/gh_stub.py`) and asserts on the calls the product builds — the product
code that decides the labels, the marker and the create/update/clear split runs for real.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import security_issues as si  # noqa: E402

POLICY = {"fail_on": ["critical", "high"], "pr_fail_on": ["critical"],
          "require_fix": True, "issue_severities": ["critical", "high"]}
#: Every label a finding can carry: what the stub answers when a label read-back is requested.
LOUD = ("security,vulnerability,severity:critical,severity:high,component:python,"
        "component:container,auto-fixable")
TRIVY = {"Results": [{"Vulnerabilities": [
    {"VulnerabilityID": "CVE-1", "PkgName": "numpy", "InstalledVersion": "1.0",
     "FixedVersion": "1.1", "Severity": "CRITICAL"},
    {"VulnerabilityID": "CVE-2", "PkgName": "libssl", "InstalledVersion": "3.0",
     "FixedVersion": "3.1", "Severity": "HIGH"},
    {"VulnerabilityID": "CVE-3", "PkgName": "gguf", "InstalledVersion": "0.1",
     "FixedVersion": "0.2", "Severity": "MEDIUM"},
]}]}


def _reports(tmp_path: Path, payload: dict = TRIVY) -> Path:
    d = tmp_path / "reports"
    d.mkdir(parents=True, exist_ok=True)
    (d / "trivy.json").write_text(json.dumps(payload), encoding="utf-8")
    return d


def _gh_stub(tmp_path: Path, monkeypatch) -> Path:
    """A real `gh` executable on PATH that appends its argv to a file."""
    log = tmp_path / "gh-calls.log"
    stub = tmp_path / "gh"
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "open(os.environ['GH_STUB_LOG'], 'a').write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "if sys.argv[1:2] == ['api'] and any('labels' in a for a in sys.argv):\n"
        f"    print(os.environ.get('GH_STUB_LABELS', '{LOUD}'))\n"
        "elif 'list' in sys.argv[1:3]:\n"
        "    print(os.environ.get('GH_STUB_LIST', '[]'))\n"
        "else:\n"
        "    print('https://github.com/o/r/issues/1')\n",
        encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")
    monkeypatch.setenv("GH_STUB_LOG", str(log))
    return log


def test_only_policy_severities_become_issues(tmp_path):
    """Critical/High with a fix become issues; Medium does not (policy, not a literal)."""

    # Given a report with CRITICAL, HIGH and MEDIUM findings
    findings = si.issue_findings(_reports(tmp_path), POLICY)

    # Then  the Medium one is not selected
    assert [f.advisory for f in findings] == ["CVE-1", "CVE-2"]


def test_a_finding_without_a_fix_gets_no_issue(tmp_path):
    """`require_fix` keeps an unfixable advisory out of the new-issue flow (it stays in the report)."""

    # Given a CRITICAL with no fixed version
    payload = {"Results": [{"Vulnerabilities": [
        {"VulnerabilityID": "CVE-9", "PkgName": "numpy", "InstalledVersion": "1.0",
         "FixedVersion": "", "Severity": "CRITICAL"}]}]}

    # When  issues are selected
    findings = si.issue_findings(_reports(tmp_path, payload), POLICY)

    # Then  nothing is filed, because nobody can act on it
    assert findings == []


def test_labels_and_components_follow_the_finding(tmp_path):
    """Every issue carries security, vulnerability, one severity, one component, and auto-fixable."""

    # Given the CRITICAL numpy (python) and HIGH libssl (container) findings
    findings = si.issue_findings(_reports(tmp_path), POLICY)

    # Then  each label set is complete and the component is the right one
    numpy = next(f for f in findings if f.package == "numpy")
    ssl = next(f for f in findings if f.package == "libssl")
    assert numpy.labels == ["security", "vulnerability", "severity:critical",
                            "component:python", "auto-fixable"]
    assert ssl.labels == ["security", "vulnerability", "severity:high",
                          "component:container", "auto-fixable"]


def test_the_marker_round_trips():
    """The marker is the idempotency key, so it must survive being written into a body."""

    # Given a finding
    finding = si.Finding("CVE-1", "numpy", "1.0", "1.1", "critical", "trivy")

    # When  its body is rendered and re-read
    body = si.body_for(finding)
    m = si.MARKER_RE.search(body)

    # Then  the key comes back exactly
    assert (m.group(1), m.group(2), m.group(3)) == ("trivy", "CVE-1", "numpy")


def test_the_body_states_advisory_package_versions_and_action(tmp_path):
    """A reviewer must learn the advisory, the package, current → fixed, the run and what to do."""

    # Given a finding from a run
    finding = si.issue_findings(_reports(tmp_path), POLICY)[0]

    # When  the issue body is rendered
    body = si.body_for(finding, "https://github.com/o/r/actions/runs/1")

    # Then  every required element is present, in the shape every issue carries (issue #745)
    for fragment in ("CVE-1", "numpy", "1.0", "1.1", "https://github.com/o/r/actions/runs/1",
                     "## Problem", "## Why it matters", "## How we fix it", "## Benefit",
                     "## Acceptance criteria", "## Not covered", "## Technical"):
        assert fragment in body, fragment

    # And the sections are in order, with the technical detail last
    assert [h for h in si.issue_body.headings(body) if h in si.issue_body.SECTIONS] == \
        list(si.issue_body.SECTIONS)
    assert si.issue_body.headings(body)[-1] == "Technical"


def _calls(log: Path) -> list[list[str]]:
    """Every argv the stub saw, parsed — so a `label create` is never mistaken for an issue create."""
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


def test_apply_creates_then_updates_the_same_issue(tmp_path, monkeypatch):
    """A second run against a known finding edits it; it never opens a duplicate."""

    # Given a gh that answers "no open security issues" then one that answers with the filed one
    log = _gh_stub(tmp_path, monkeypatch)
    findings = si.issue_findings(_reports(tmp_path), POLICY)

    # When  apply runs on a clean tracker
    si.apply(findings, "o/r")
    creates = [c for c in _calls(log) if c[:2] == ["issue", "create"]]

    # Then  one create per finding, each with its labels
    assert len(creates) == 2
    assert all("--label" in l and "auto-fixable" in l for l in creates)

    # And when the tracker already carries the markers, the same run edits instead of creating
    log.unlink()
    existing = [{"number": 7, "body": findings[0].marker, "labels": [], "title": "t"},
                {"number": 8, "body": findings[1].marker, "labels": [], "title": "t"}]
    monkeypatch.setenv("GH_STUB_LIST", json.dumps(existing))
    si.apply(findings, "o/r")
    calls = _calls(log)
    assert not [c for c in calls if c[:2] == ["issue", "create"]]
    assert len([c for c in calls if c[:2] == ["issue", "edit"]]) == 2


def test_a_dropped_label_fails_the_step_instead_of_filing_an_invisible_issue(tmp_path, monkeypatch):
    """The label is probed, not assumed: create's `--label` is dropped on the runner path (#724)."""

    # Given a gh whose label read-back answers with one label whatever was written
    log = _gh_stub(tmp_path, monkeypatch)
    findings = si.issue_findings(_reports(tmp_path), POLICY)
    monkeypatch.setenv("GH_STUB_LABELS", "security")

    # When  apply files an issue whose labels did not stick
    try:
        si.apply(findings, "o/r")
    except SystemExit as exc:
        assert "invisible to the bot that fixes it" in str(exc), exc
    else:                                        # pragma: no cover - the failure is the assertion
        raise AssertionError("an unlabelled issue must fail the step")

    # Then  the explicit POST was attempted first (create's --label is never the whole write)
    assert [c for c in _calls(log) if c[:1] == ["api"] and "-X" in c and "POST" in c]


def test_the_label_read_back_is_what_the_issue_carries(tmp_path, monkeypatch):
    """A successful run proves the labels by reading them back, not by trusting the create flag."""

    # Given a tracker that keeps the labels
    log = _gh_stub(tmp_path, monkeypatch)

    # When  apply files the findings
    si.apply(si.issue_findings(_reports(tmp_path), POLICY), "o/r")

    # Then  every created issue was followed by a POST and a read-back
    calls = _calls(log)
    posts = [c for c in calls if c[:1] == ["api"] and "-X" in c and "POST" in c]
    reads = [c for c in calls if c[:1] == ["api"] and "repos/o/r/issues/1/labels" in c
             and "--jq" in c]
    assert len(posts) == 2 and len(reads) == 2


def test_a_vanished_finding_is_closed(tmp_path, monkeypatch):
    """An advisory the scanner no longer reports is cleared, with the reason recorded."""

    # Given a tracker entry for a finding the current report does not contain
    log = _gh_stub(tmp_path, monkeypatch)
    ghost = "<!-- security-finding: trivy:CVE-OLD:numpy -->"
    monkeypatch.setenv("GH_STUB_LIST", json.dumps(
        [{"number": 9, "body": ghost, "labels": [], "title": "old"}]))

    # When  apply runs for a report without it
    si.apply(si.issue_findings(_reports(tmp_path), POLICY), "o/r")

    # Then  it is closed with a comment naming the run
    closes = [c for c in _calls(log) if c[:2] == ["issue", "close"]]
    assert len(closes) == 1 and "9" in closes[0]


def test_plan_classifies_without_mutating(tmp_path):
    """`plan` is what `DRY=1` prints; it must split create/update/clear and write nothing."""

    # Given two findings and one existing issue
    findings = si.issue_findings(_reports(tmp_path), POLICY)
    existing = {findings[0].key: {"number": 1, "body": "", "labels": [], "title": ""},
                "trivy:CVE-GONE:numpy": {"number": 2, "body": "", "labels": [], "title": ""}}

    # When  the plan is computed
    actions = si.plan(findings, existing)

    # Then  one create, one update, one clear
    assert [f.key for f in actions["create"]] == [findings[1].key]
    assert [f.key for f in actions["update"]] == [findings[0].key]
    assert actions["clear"] == ["trivy:CVE-GONE:numpy"]


def test_the_real_policy_and_labels_are_sane():
    """The shipped policy, the label roster and the marker must agree."""

    # Given this repository
    # When  the gate runs
    rc = si.check()

    # Then  it passes
    assert rc == 0
