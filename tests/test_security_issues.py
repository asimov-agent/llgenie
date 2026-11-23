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
from scripts import security_issues as si
from scripts import security_scan as ss

POLICY = {"fail_on": ["critical", "high"], "pr_fail_on": ["critical"],
          "require_fix": True, "issue_severities": ["critical", "high"]}
#: Every label a finding can carry: the roster the label tests seed an issue with.
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
    """A real `gh` executable on PATH that appends its argv to a file.

    Its issue-label endpoint has STATE (issue #3036): what an issue carries starts as
    `GH_STUB_LABELS` (empty by default — `gh issue create --label` is measured to drop labels, #724),
    a `POST .../labels` merges the labels it names, `DELETE .../labels/<name>` removes one, and a GET
    answers with what that issue then carries. `GH_STUB_LABEL_WRITE=ignore` makes both writes no-ops —
    the shape of a label write that did not stick. Each `issue create` is handed the NEXT issue number,
    so two findings filed in one run are two issues with two label sets, as on the real tracker.
    """
    log = tmp_path / "gh-calls.log"
    stub = tmp_path / "gh"
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "open(os.environ['GH_STUB_LOG'], 'a').write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "ST = os.environ['GH_STUB_LABEL_STATE']\n"
        "def issue_no():\n"
        "    for a in sys.argv:\n"
        "        if '/labels' in a:\n"
        "            return a.split('/labels', 1)[0].rsplit('/', 1)[1]\n"
        "    return '1'\n"
        "def store():\n"
        "    s = json.loads(open(ST).read()) if os.path.exists(ST) else {}\n"
        "    if issue_no() not in s:\n"
        "        s[issue_no()] = [x.strip() for x in os.environ.get('GH_STUB_LABELS', '').split(',') if x.strip()]\n"
        "    return s\n"
        "def carry():\n"
        "    return store()[issue_no()]\n"
        "def save(cur):\n"
        "    s = json.loads(open(ST).read()) if os.path.exists(ST) else {}\n"
        "    s[issue_no()] = cur\n"
        "    open(ST, 'w').write(json.dumps(s))\n"
        "def writes_stick():\n"
        "    return os.environ.get('GH_STUB_LABEL_WRITE', 'stick') == 'stick'\n"
        "if sys.argv[1:2] == ['api'] and any('comments' in a for a in sys.argv):\n"
        "    print(os.environ.get('GH_STUB_COMMENTS', '[]'))\n"
        "elif '--state' in sys.argv and 'closed' in sys.argv and 'issue' in sys.argv:\n"
        "    print(os.environ.get('GH_STUB_CLOSED', '[]'))\n"
        "elif sys.argv[1:2] == ['api'] and any('/labels' in a for a in sys.argv):\n"
        "    cur = carry()\n"
        "    if '-X' in sys.argv and 'POST' in sys.argv and writes_stick():\n"
        "        for a in sys.argv:\n"
        "            if a.startswith('labels[]') and a.split('=', 1)[1] not in cur:\n"
        "                cur.append(a.split('=', 1)[1])\n"
        "        save(cur)\n"
        "    elif '-X' in sys.argv and 'DELETE' in sys.argv and writes_stick():\n"
        "        for a in sys.argv:\n"
        "            if '/labels/' in a:\n"
        "                gone = a.rsplit('/labels/', 1)[1]\n"
        "                if gone in cur:\n"
        "                    cur.remove(gone)\n"
        "        save(cur)\n"
        "    print('\\n'.join(cur))\n"
        "elif 'list' in sys.argv[1:3]:\n"
        "    print(os.environ.get('GH_STUB_LIST', '[]'))\n"
        "elif sys.argv[1:2] == ['issue'] and 'create' in sys.argv:\n"
        "    n, c = 1, ST + '.counter'\n"
        "    if os.path.exists(c):\n"
        "        n = int(open(c).read())\n"
        "    open(c, 'w').write(str(n + 1))\n"
        "    print(f'https://github.com/o/r/issues/{n}')\n"
        "else:\n"
        "    print('https://github.com/o/r/issues/1')\n",
        encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")
    monkeypatch.setenv("GH_STUB_LOG", str(log))
    monkeypatch.setenv("GH_STUB_LABEL_STATE", str(tmp_path / "gh-label-state.json"))
    return log


def _label_state(tmp_path: Path) -> dict[str, list[str]]:
    """What the stub tracker says each issue actually carries, per issue number."""
    p = tmp_path / "gh-label-state.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


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


def test_a_committed_secret_becomes_an_issue_despite_no_fix(tmp_path):
    """A committed credential has no 'fixed version' but is ALWAYS actionable (remove and rotate):
    `require_fix` must not keep it off the tracker — it gets a `component:code` issue (issue #1283)."""

    # Given a trivy report carrying a CRITICAL committed secret (a `trivy-secret` finding, no fix)
    payload = {"Results": [{"Target": "tools/api_key.py", "Secrets": [
        {"RuleID": "github-pat", "Severity": "CRITICAL", "Match": "ghp_*****************"}]}]}
    d = _reports(tmp_path, payload)

    # When  issues are selected under the policy (require_fix on)
    findings = si.issue_findings(d, POLICY)

    # Then  the secret becomes an issue, labelled as code (not python/container)
    assert len(findings) == 1
    f = findings[0]
    assert f.advisory == "github-pat" and f.package == "tools/api_key.py"
    assert f.source == "trivy-secret" and f.fixed == ""
    assert f.component == "component:code"
    assert "auto-fixable" not in f.labels  # a secret is removed, never version-bumped
    assert "severity:critical" in f.labels


def test_a_semgrep_sast_finding_becomes_an_issue_despite_no_fix(tmp_path):
    """A SAST finding has no 'fixed version' but is ALWAYS actionable (edit the matched code):
    `require_fix` must not keep it off the tracker — it gets a `component:code` issue, and never an
    `auto-fixable` (a bump cannot fix code), mirroring the committed-secret case (issue #1554)."""

    # Given a semgrep report with one ERROR finding (a raw-SQL execution pattern)
    payload = {"results": [{
        "check_id": "python.sqlalchemy.security.sqlalchemy-execute-raw-query",
        "path": "tools/app.py", "start": {"line": 5, "col": 12},
        "extra": {"severity": "ERROR", "lines": "    engine.execute(text(query))"},
    }]}
    d = tmp_path / "reports"  # this helper writes trivy.json only, so add semgrep.json by hand
    d.mkdir(parents=True, exist_ok=True)
    (d / "semgrep.json").write_text(json.dumps(payload), encoding="utf-8")

    # When  issues are selected under the policy (require_fix on)
    findings = si.issue_findings(d, POLICY)

    # Then  the SAST finding becomes a code issue despite no fixed version
    assert len(findings) == 1
    f = findings[0]
    assert f.advisory == "python.sqlalchemy.security.sqlalchemy-execute-raw-query"
    assert f.package == "tools/app.py:5"
    assert f.source == "semgrep" and f.fixed == ""
    assert f.severity == "high"  # ERROR mapped into the gated vocabulary
    assert f.component == "component:code"
    assert "auto-fixable" not in f.labels  # a bump cannot fix code
    assert "severity:high" in f.labels


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


def test_an_image_scanned_finding_is_a_container_finding_named_by_its_digest(tmp_path):
    """A numpy HIGH finding found INSIDE a published image is `component:container` (the defect is
    in the built artifact) and its issue body names the exact `ref@digest` it lives in (issue #2706)."""

    # Given an image report + meta in the same reports dir (the shape security_scan writes)
    d = tmp_path / "reports"
    d.mkdir()
    (d / "image-llama-cpp-cuda.trivy.json").write_text(json.dumps({
        "Results": [{"Vulnerabilities": [
            {"VulnerabilityID": "CVE-9", "PkgName": "numpy", "InstalledVersion": "1.0",
             "FixedVersion": "1.1", "Severity": "HIGH"}]}]}), encoding="utf-8")
    image = "ghcr.io/asimov-agent/llgenie/llama-cpp:deadbeef-cuda@sha256:" + "ab" * 32
    (d / "image-llama-cpp-cuda.meta.json").write_text(json.dumps({"ref": image}), encoding="utf-8")

    # When  the finding becomes an issue candidate
    finding = next(f for f in si.issue_findings(d, POLICY) if f.advisory == "CVE-9")

    # Then  it carries the image, is a container finding whatever the package family, and labels so
    assert finding.image == image
    assert finding.component == "component:container"
    assert "component:container" in finding.labels

    # And   the body names the exact digest, not just the package
    body = si.body_for(finding, "https://github.com/o/r/actions/runs/1")
    assert image in body


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


def test_an_sast_body_tells_the_reader_to_edit_the_code():
    """A `component:code` SAST body names EDITING THE SOURCE, not a nonexistent pin bump.

    The marker (idempotency key), advisory id, severity, component and run link are identical to the
    CVE body; only the remediation prose differs (issue #1560).
    """

    # Given a semgrep SAST finding (no fixed version; lives in a file, not a requirements pin)
    finding = si.Finding(
        advisory="python.sqlalchemy.security.sqlalchemy-execute-raw-query",
        package="tools/app.py:5", current="engine.execute(text(query))", fixed="",
        severity="high", source="semgrep", component="component:code",
    )

    # When  its issue body is rendered
    body = si.body_for(finding, "https://github.com/o/r/actions/runs/1")

    # Then  it tells the reader to EDIT the matched source, present-tense
    assert "Edit the matched region in `tools/app.py:5`" in body
    assert "no longer triggers" in body

    # And it does NOT tell the reader to bump a pin in the generated requirements*.txt path
    assert "requirements*.txt" not in body
    assert "generated `tools/requirements*.in`" not in body
    assert "(no fixed version named)" not in body

    # And the marker (idempotency key) round-trips unchanged
    m = si.MARKER_RE.search(body)
    assert m is not None and (m.group(1), m.group(2), m.group(3)) == (
        "semgrep", "python.sqlalchemy.security.sqlalchemy-execute-raw-query", "tools/app.py:5")
    # And the traceability fields are the code body's own, not the pin template's
    assert "**Component:** `component:code`" in body
    assert "https://github.com/o/r/actions/runs/1" in body


def test_a_cve_body_still_tells_the_reader_to_bump_the_pin(tmp_path):
    """A CVE finding keeps the pin/requirements* wording — the fix is shape-only for code."""

    # Given a trivy python finding with a fixed version
    finding = si.Finding("CVE-1", "numpy", "1.0", "1.1", "critical", "trivy",
                         component="component:python")

    # When  its body is rendered
    body = si.body_for(finding)

    # Then  it still names the generated requirements*.txt pin path and the bump action
    assert "generated `tools/requirements*.in` -> `requirements*.txt` path" in body
    assert "is pinned at `1.1` or later in the compiled `requirements*.txt`" in body
    assert "EDIT the matched" not in body


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

    # Given a gh whose label writes do not stick: whatever is POSTed, the issue keeps carrying the
    # one label it started with
    log = _gh_stub(tmp_path, monkeypatch)
    findings = si.issue_findings(_reports(tmp_path), POLICY)
    monkeypatch.setenv("GH_STUB_LABELS", "security")
    monkeypatch.setenv("GH_STUB_LABEL_WRITE", "ignore")

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

    # Then  every created issue was followed by a POST and a read-back of ITS OWN labels
    calls = _calls(log)
    posts = [c for c in calls if c[:1] == ["api"] and "-X" in c and "POST" in c]
    reads = [c for c in calls if c[:1] == ["api"] and "--jq" in c
             and any(a.endswith("/labels") for a in c)]
    assert len(posts) == 2 and len(reads) == 2
    assert sorted({c[3].split("/")[4] for c in posts}) == ["1", "2"]


def test_a_relabelled_finding_loses_its_stale_component_label(tmp_path, monkeypatch, capsys):
    """The label set is RECONCILED, not only added (issue #3036): an open issue first filed as
    `component:python` for an advisory the published-image scan now reports must stop routing to the
    dependency lane that has nothing to move (the measured #3025 shape)."""

    # Given an open issue that carries a python component label, and the same advisory arriving as a
    # container finding
    log = _gh_stub(tmp_path, monkeypatch)
    finding = next(f for f in si.issue_findings(_reports(tmp_path), POLICY) if f.advisory == "CVE-2")
    assert finding.component == "component:container"
    monkeypatch.setenv("GH_STUB_LIST", json.dumps(
        [{"number": 42, "body": finding.marker, "labels": [], "title": "t"}]))
    monkeypatch.setenv("GH_STUB_LABELS",
                       "security,vulnerability,severity:high,component:python,auto-fixable")

    # When  the run files the finding onto that issue
    si.apply([finding], "o/r")

    # Then  the label it no longer earns came off by an explicit DELETE
    dels = [c for c in _calls(log) if c[:1] == ["api"] and "-X" in c and "DELETE" in c]
    assert len(dels) == 1, dels
    assert "repos/o/r/issues/42/labels/component:python" in " ".join(dels[0]), dels

    # And   the removal is proven by a read-back: the issue carries the container label, no python
    # one, and kept its severity and auto-fixable labels
    carried = _label_state(tmp_path)["42"]
    assert "component:container" in carried and "component:python" not in carried, carried
    assert "severity:high" in carried and "auto-fixable" in carried, carried
    assert "re-labelled #42: removed component:python" in capsys.readouterr().out


def test_a_component_label_that_will_not_come_off_fails_the_step(tmp_path, monkeypatch):
    """An unproven removal fails the step (issue #3036): a stale component label routes the issue to
    an owner who has nothing to change, exactly like a missing label does."""

    # Given an issue that carries every label in the roster, in a gh whose label writes do not stick
    _gh_stub(tmp_path, monkeypatch)
    monkeypatch.setenv("GH_STUB_LABELS", LOUD)
    monkeypatch.setenv("GH_STUB_LABEL_WRITE", "ignore")

    # When  the labels are reconciled onto it (python out, container in)
    try:
        si.set_labels("o/r", 42, ["security", "vulnerability", "severity:high",
                                  "component:container", "auto-fixable"])
    except SystemExit as exc:
        assert "still carries component:python" in str(exc), str(exc)
    else:                                        # pragma: no cover - the failure is the assertion
        raise AssertionError("a stale component label survived the removal check")


def test_an_image_finding_names_the_image_owner_not_the_pin_path():
    """A finding inside a published image gets the *change-the-image* body: it names the artifact and
    the `owner` file its allow-list entry points at, and never the generated requirements* pin path
    (issue #3036 — #3025's acceptance criterion asked for a `requirements*.txt` entry for a Go module
    no requirements file in this repository contains)."""

    # Given a finding reported inside the agent image the shipped allow-list scans
    shipped = next(e for e in ss.scanned_images()["images"] if e.get("name") == "agent")
    image = shipped["ref"] + "@sha256:" + "ab" * 32
    finding = si.Finding(advisory="GHSA-2c6x-4m7v-9q3d", package="github.com/gin-gonic/gin",
                         current="v1.10.0", fixed="v1.10.1", severity="high", source="trivy",
                         component="component:container", image=image)

    # When  its issue body is rendered
    body = si.body_for(finding, "https://github.com/o/r/actions/runs/1")

    # Then  it names the exact image and the file that owns it
    assert image in body
    assert "containers/agent/Dockerfile" in body, body
    assert "`make security-scan TOOL=trivy`" in body

    # And   it sends the reader to NO dependency pin path anywhere in the body
    assert "tools/requirements" not in body
    assert "generated `tools/requirements*.in`" not in body
    assert "requirements*.txt` entry" not in body

    # And   the six-section shape and the marker (idempotency key) are unchanged
    assert [h for h in si.issue_body.headings(body) if h in si.issue_body.SECTIONS] == \
        list(si.issue_body.SECTIONS)
    m = si.MARKER_RE.search(body)
    assert m is not None and (m.group(1), m.group(2), m.group(3)) == (
        "trivy", "GHSA-2c6x-4m7v-9q3d", "github.com/gin-gonic/gin")

    # And   an image the allow-list has no entry for says so plainly instead of inventing an owner
    stray = si.Finding(advisory="GHSA-0000-0000-0000", package="github.com/x/y", current="v1",
                       fixed="v2", severity="high", source="trivy",
                       component="component:container",
                       image="ghcr.io/example/not-in-the-allow-list:1@sha256:" + "cd" * 32)
    stray_body = si.body_for(stray, "")
    assert "names no owner" in stray_body, stray_body
    assert "containers/scanned-images.json" in stray_body
    assert "tools/requirements" not in stray_body


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


def _scan_evidence_issue(number: int, finding) -> dict:
    """A closed scan-evidence issue: the marker AND the acceptance round-trip line are in the body."""
    body = si.body_for(finding, "https://github.com/o/r/actions/runs/1")
    assert si.SCAN_EVIDENCE_ACCEPTANCE in body  # the template carries the round-trip acceptance
    return {"number": number, "body": body, "labels": [], "title": "n"}


def test_a_merged_pr_closes_never_clears_a_still_reported_scan_evidence_issue(tmp_path, monkeypatch):
    """A closed-by-reference scan-evidence issue whose finding is STILL scanned is reopened, not cleared.

    The #1693 defect: a merged PR's bare `closes #N` (no pipeline clearing comment) left the issue
    closed while the finding persists. Reconcile must reopen it and flag that the merge-close did
    not satisfy the acceptance box — never leave a live finding off the board (which would let the
    next `apply` re-file it as a duplicate).
    """
    finding = si.Finding("CVE-1", "numpy", "1.0", "1.1", "critical", "trivy",
                         component="component:python")
    log = _gh_stub(tmp_path, monkeypatch)
    monkeypatch.setenv("GH_STUB_CLOSED", json.dumps([_scan_evidence_issue(9, finding)]))
    monkeypatch.setenv("GH_STUB_COMMENTS", "[]")  # closed by a merged PR, not by the pipeline

    si.reconcile([finding], "o/r", run_url="https://github.com/o/r/actions/runs/42",
                 sha="abc123")

    calls = _calls(log)
    reopens = [c for c in calls if c[:2] == ["issue", "reopen"] and "9" in c]
    comments = [c for c in calls if c[:2] == ["issue", "comment"] and "9" in c]
    assert len(reopens) == 1, reopens
    assert reopens[0][2] == "9", reopens
    # issue #2621: the old form `gh issue edit <n> --state open` is not a valid gh call
    # (`gh issue edit` has no --state flag) and reddened every daily reconcile for 6 runs.
    assert not any(c[:2] == ["issue", "edit"] and "--state" in c for c in calls), calls
    assert len(comments) == 1, comments
    joined = " ".join(comments[0])
    assert "does not satisfy a scan-evidence acceptance box" in joined, joined
    assert "still reports this finding" in joined, joined


def test_a_merged_pr_closed_issue_with_the_finding_gone_gets_the_run_sha_evidence_comment(
        tmp_path, monkeypatch):
    """The finding is genuinely absent on a real scan — post the run id + sha round-trip comment.

    The merge-close skipped the honest #1646 comment; a later scan that no longer reports the
    finding satisfies the box honestly, and the comment must name run id + sha (criterion #2).
    """
    finding = si.Finding("CVE-1", "numpy", "1.0", "1.1", "critical", "trivy",
                         component="component:python")
    log = _gh_stub(tmp_path, monkeypatch)
    monkeypatch.setenv("GH_STUB_CLOSED", json.dumps([_scan_evidence_issue(9, finding)]))
    monkeypatch.setenv("GH_STUB_COMMENTS", "[]")

    si.reconcile([], "o/r", run_url="https://o/r/actions/runs/99", sha="deadbeef")

    calls = _calls(log)
    comments = [c for c in calls if c[:2] == ["issue", "comment"] and "9" in c]
    assert len(comments) == 1, comments
    joined = " ".join(comments[0])
    assert "No longer reported by the latest scan" in joined, joined
    assert "https://o/r/actions/runs/99" in joined, joined   # run id
    assert "deadbeef" in joined, joined                       # sha


def test_a_genuine_pipeline_clear_is_left_untouched(tmp_path, monkeypatch):
    """A closed issue that DOES carry the pipeline's clearing comment is never acted on.

    Criterion #4 — no behaviour change for the honest loop: reconcile reads CLEAR_COMMENT back from
    the live tracker and skips issues the pipeline itself already cleared with evidence.
    """
    finding = si.Finding("CVE-1", "numpy", "1.0", "1.1", "critical", "trivy",
                         component="component:python")
    log = _gh_stub(tmp_path, monkeypatch)
    monkeypatch.setenv("GH_STUB_CLOSED", json.dumps([_scan_evidence_issue(9, finding)]))
    monkeypatch.setenv("GH_STUB_COMMENTS",
                       json.dumps([{"body": "No longer reported by the latest scan "
                                             "(https://o/r/actions/runs/1)."}]))

    si.reconcile([finding], "o/r")  # even though the finding is still scanned, the clear stands

    calls = _calls(log)
    assert not [c for c in calls if c[:2] == ["issue", "edit"]], calls
    assert not [c for c in calls if c[:2] == ["issue", "comment"]], calls


def test_reconcile_dry_modifies_nothing(tmp_path, monkeypatch):
    """`--dry` prints the merged-PR-close detection and defers every write (plan-first discipline)."""
    finding = si.Finding("CVE-1", "numpy", "1.0", "1.1", "critical", "trivy",
                         component="component:python")
    log = _gh_stub(tmp_path, monkeypatch)
    monkeypatch.setenv("GH_STUB_CLOSED", json.dumps(
        [_scan_evidence_issue(9, finding), _scan_evidence_issue(10, finding)]))
    monkeypatch.setenv("GH_STUB_COMMENTS", "[]")

    si.reconcile([finding], "o/r", dry=True)

    calls = _calls(log)
    assert calls, "reconcile --dry must still READ the tracker"
    assert not [c for c in calls if c[:2] == ["issue", "edit"]], calls
    assert not [c for c in calls if c[:2] == ["issue", "comment"]], calls
