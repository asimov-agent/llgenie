"""The scan pipeline (issue #715): one invocation seam, one policy, pinned scanner images.

Every rule is proven on a fixture, then the real tree is asserted sane: the policy decides what
fails (full vs pull-request mode), a finding without a fix never blocks, a report that cannot be
parsed is never a pass, and the workflow references the scanner images from `digests.json` rather
than a tag. No Docker and no network: the scanners themselves are exercised by the
`security-scan` CI job (`make security-scan-all`).

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

import json
import os
import re
import stat
import sys
import time

import pytest

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
from scripts import security_scan as ss

TRIVY_OK = {"Results": [{"Vulnerabilities": [
    {"VulnerabilityID": "CVE-1", "PkgName": "numpy", "InstalledVersion": "1.0",
     "FixedVersion": "1.1", "Severity": "CRITICAL"},
]}]}
TRIVY_NO_FIX = {"Results": [{"Vulnerabilities": [
    {"VulnerabilityID": "CVE-2", "PkgName": "gguf", "InstalledVersion": "0.1",
     "FixedVersion": "", "Severity": "CRITICAL"},
]}]}
TRIVY_HIGH = {"Results": [{"Vulnerabilities": [
    {"VulnerabilityID": "CVE-3", "PkgName": "numpy", "InstalledVersion": "1.0",
     "FixedVersion": "1.2", "Severity": "HIGH"},
]}]}
# A committed credential (issue #1283): trivy's `secret` scanner writes a `Secrets` array under the
# result, carrying a RuleID, a Severity and a redacted Match — no package and no fixed version.
TRIVY_SECRET = {"Results": [{"Target": "tools/api_key.py", "Secrets": [
    {"RuleID": "github-pat", "Category": "GitHub", "Severity": "CRITICAL",
     "Title": "GitHub Personal Access Token", "Match": "ghp_****************************"},
]}]}
TRIVY_SECRET_MEDIUM = {"Results": [{"Target": "tools/timeout.py", "Secrets": [
    {"RuleID": "generic-api-key", "Category": "Generic", "Severity": "MEDIUM",
     "Match": "sk-*******************************"},
]}]}
# An IaC misconfiguration (issue #2234): trivy's `misconfig` scanner writes a `Misconfigurations`
# array under a result whose `Class` is `config` (the vuln/secret results carry `Class`
# `os-pkgs`/`lang-pkgs`/absent). The shape is the real JSON the pinned trivy image emits for a
# planted bad Dockerfile (a missing non-root `USER` → `DS-0002`), measured 2026-11-08: ID, Title,
# Severity, Message — no package version and no fixed version.
TRIVY_MISCONFIG = {"Results": [{
    "Target": "containers/example/Dockerfile", "Class": "config", "Type": "dockerfile",
    "Misconfigurations": [{
        "ID": "DS-0002", "Title": "Image user should not be 'root'", "Severity": "HIGH",
        "Message": "Specify at least 1 USER command in Dockerfile with non-root user as argument",
        "Namespace": "builtin.dockerfile.DS002", "Query": "data.builtin.dockerfile.DS002.deny",
        "PrimaryURL": "https://avd.aquasec.com/misconfig/ds-0002", "Status": "FAIL",
    }],
}]}
TRIVY_MISCONFIG_MEDIUM = {"Results": [{
    "Target": ".github/workflows/deploy.yml", "Class": "config", "Type": "github actions",
    "Misconfigurations": [{
        "ID": "AVD-EXAMPLE-1", "Title": "workflow drift", "Severity": "MEDIUM",
        "Message": "a workflow gift", "Status": "FAIL",
    }],
}]}
GRYPE_ONE = {"matches": [{
    "vulnerability": {"id": "GHSA-1", "severity": "Critical"},
    "artifact": {"name": "openssl", "version": "3.0"},
    "fix": {"versions": ["3.1"]},
}]}
# A Semgrep SAST block (issue #1554): the real `semgrep.json` shape a committed-pack run writes — one
# result per fired rule, each with a check_id, a path, a start line and the matched region in
# `extra.lines`, and a rule severity of ERROR/WARNING/INFO (NOT the policy's critical/high/…).
SEMGREP_ONE = {"results": [{
    "check_id": "python.sqlalchemy.security.sqlalchemy-execute-raw-query",
    "path": "app.sql.py", "start": {"line": 5, "col": 12},
    "extra": {"severity": "ERROR", "lines": "    engine.execute(text(query))"},
}]}
SEMGREP_WARNING = {"results": [{
    "check_id": "python.lang.security.audit.formatted-sql-query",
    "path": "app.sql.py", "start": {"line": 8, "col": 12},
    "extra": {"severity": "WARNING", "lines": "    cursor.execute(f\"SELECT * FROM t WHERE a = {x}\")"},
}]}

POLICY = {"fail_on": ["critical", "high"], "pr_fail_on": ["critical"],
          "require_fix": True, "issue_severities": ["critical", "high"]}


def _reports(tmp_path: Path, **files) -> Path:
    d = tmp_path / "reports"
    d.mkdir(parents=True, exist_ok=True)
    for name, payload in files.items():
        (d / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")
    return d


def test_trivy_findings_are_normalised():
    """A trivy report becomes one shape with id, package, current, fixed and severity."""

    # Given a trivy report with one CRITICAL that has a fix
    # When  it is normalised
    items = ss._trivy_findings(TRIVY_OK)

    # Then  every field a remediation needs is present
    assert items == [{"id": "CVE-1", "package": "numpy", "current": "1.0",
                      "fixed": "1.1", "severity": "critical", "source": "trivy"}]


def test_trivy_secret_findings_are_normalised():
    """A committed credential (a trivy `secret`-class match) is a first-class finding (issue #1283)."""

    # Given a trivy report with one CRITICAL committed secret against a file
    # When  it is normalised
    items = ss._trivy_secret_findings(TRIVY_SECRET)

    # Then  the finding names the file (not a package), has no fixed version, and carries the
    #       distinct `trivy-secret` source so the issue path labels it `component:code`
    assert items == [{"id": "github-pat", "package": "tools/api_key.py", "current": "ghp_****************************",
                      "fixed": "", "severity": "critical", "source": "trivy-secret"}]


def test_a_committed_secret_flows_through_findings(tmp_path, monkeypatch):
    """The dedicated secret classifier is read by the same `findings()` gate as the scanners."""

    # Given a trivy report that also carries a committed secret
    report = {"Results": [
        {"Target": "tools/requirements.txt", "Vulnerabilities": [
            {"VulnerabilityID": "CVE-1", "PkgName": "numpy", "InstalledVersion": "1.0",
             "FixedVersion": "1.1", "Severity": "CRITICAL"}]},
        {"Target": "tools/api_key.py", "Secrets": [
            {"RuleID": "github-pat", "Severity": "CRITICAL", "Match": "ghp_x"}]},
    ]}
    monkeypatch.setattr(ss, "REPORTS", _reports(tmp_path, trivy=report))

    # When  findings are read
    items = ss.findings()

    # Then  both the advisory and the committed secret are present, in the fixed finding shape
    assert any(i["source"] == "trivy" and i["id"] == "CVE-1" for i in items)
    assert any(i["source"] == "trivy-secret" and i["id"] == "github-pat" for i in items)


def test_a_critical_committed_secret_blocks_even_with_require_fix(tmp_path, monkeypatch):
    """A committed credential has no 'fixed version' to wait for — `require_fix` must not the
    daily gate ignore it: removal is the remediation, so it blocks at `fail_on` (issue #1283)."""

    # Given a CRITICAL committed secret in the report (no package, no fixed version)
    items = ss._trivy_secret_findings(TRIVY_SECRET)

    # When  the FULL (gating) policy is applied with require_fix on (the shipped default)
    bad = ss.blocking(items, POLICY, "full")

    # Then  it blocks — a committed secret is always actionable (remove and rotate, never wait)
    assert [i["id"] for i in bad] == ["github-pat"]
    assert ss.blocking(items, dict(POLICY, require_fix=True), "full") != []


def test_a_medium_committed_secret_is_recorded_never_blocking():
    """`fail_on` still gates a committed secret: MEDIUM is recorded, never a red (issue #1283)."""

    # Given a MEDIUM committed secret
    items = ss._trivy_secret_findings(TRIVY_SECRET_MEDIUM)

    # When  the full policy is applied
    bad = ss.blocking(items, POLICY, "full")

    # Then  it is not blocking (only critical/high gate), and the report-only PR mode is empty too
    assert bad == []
    assert ss.blocking(items, POLICY, "pr") == []


def test_semgrep_findings_are_normalised():
    """A Semgrep result becomes one finding with the policy's severity vocabulary (issue #1554)."""

    # Given a Semgrep report with one ERROR and one WARNING result
    # When  it is normalised
    items = ss._semgrep_findings(SEMGREP_ONE) + ss._semgrep_findings(SEMGREP_WARNING)

    # Then  the ERROR maps to `high` (in `fail_on`), the WARNING to `medium`, both carry the SAST
    #       source, name the file path:line and hold the matched region with no fixed version
    error, warning = items[0], items[1]
    assert error == {"id": "python.sqlalchemy.security.sqlalchemy-execute-raw-query",
                     "package": "app.sql.py:5", "current": "    engine.execute(text(query))",
                     "fixed": "", "severity": "high", "source": "semgrep"}
    assert warning["severity"] == "medium"
    assert warning["package"] == "app.sql.py:8"
    assert {i["source"] for i in items} == {ss.SEMGREP_SOURCE}


def test_a_semgrep_finding_flows_through_findings(tmp_path, monkeypatch):
    """The SAST report is read by the same `findings()` gate as the CVE scanners (issue #1554)."""

    # Given a reports dir with one advisory and one ERROR-severity semgrep finding
    report = {"results": [SEMGREP_ONE["results"][0]]}
    monkeypatch.setattr(ss, "REPORTS", _reports(tmp_path, trivy=TRIVY_OK,
                                                **{"semgrep": report}))

    # When  findings are read
    items = ss.findings()

    # Then  both the advisory and the SAST finding are present, in the fixed finding shape
    assert any(i["source"] == "trivy" and i["id"] == "CVE-1" for i in items)
    assert any(i["source"] == "semgrep"
               and i["id"] == "python.sqlalchemy.security.sqlalchemy-execute-raw-query"
               for i in items)


def test_an_error_semgrep_finding_blocks_even_with_require_fix():
    """A SAST finding has no 'fixed version' to wait for — `require_fix` must not let the daily gate
    ignore it: editing the matched code is the remediation, so an ERROR blocks at `fail_on`
    (issue #1554)."""

    # Given an ERROR-severity semgrep finding at the gated severity (mapped to `high`)
    items = ss._semgrep_findings(SEMGREP_ONE)

    # When  the FULL (gating) policy is applied with require_fix on (the shipped default)
    bad = ss.blocking(items, POLICY, "full")

    # Then  it blocks — editing the code is always actionable, never "await a patched version"
    assert [i["id"] for i in bad] == ["python.sqlalchemy.security.sqlalchemy-execute-raw-query"]
    assert ss.blocking(items, dict(POLICY, require_fix=True), "full") != []


def test_a_semgrep_warning_is_recorded_never_blocking():
    """`fail_on` still gates a SAST finding: WARNING (→ medium) is recorded, never a red (#1554)."""

    # Given a WARNING-severity semgrep finding (a likely-but-not-definite pattern)
    items = ss._semgrep_findings(SEMGREP_WARNING)

    # When  the full policy is applied
    bad = ss.blocking(items, POLICY, "full")

    # Then  it is not blocking (only critical/high gate), and the report-only PR mode is empty too
    assert bad == []
    assert ss.blocking(items, POLICY, "pr") == []


def test_trivy_runs_all_three_scanners(tmp_path, monkeypatch):
    """The daily scan asks the SAME pinned trivy image for its `secret` and `misconfig` rulesets
    too (issues #1283, #2234)."""

    # Given a docker stub that records its argv
    log = _docker_stub(tmp_path, monkeypatch, pull_ok=True, inspect_ok=True)

    # When  a trivy scan is launched
    ss.scan("trivy")

    # Then  both runs carry `--scanners vuln,secret,misconfig` — a committed secret and an IaC
    #       misconfiguration are in scope, always
    runs = [json.loads(l) for l in log.read_text().splitlines() if json.loads(l)[0] == "run"]
    assert len(runs) == 2  # JSON verdict + SARIF
    for argv in runs:
        scanners = argv[argv.index("--scanners") + 1]
        assert set(scanners.split(",")) == {"vuln", "secret", "misconfig"}, scanners
        for req in ("vuln", "secret", "misconfig"):
            assert req in scanners


def test_trivy_misconfig_findings_are_normalised():
    """An IaC misconfiguration (a trivy `misconfig`-class match) is a first-class finding (issue
    #2234)."""

    # Given a trivy report with one HIGH misconfiguration against a Dockerfile
    # When  it is normalised
    items = ss._trivy_misconfig_findings(TRIVY_MISCONFIG)

    # Then  it is one finding with the misconfig source, no package or fixed version — its fix is
    #       editing the matched IaC, so the issue path labels it `component:code`
    assert items == [{
        "id": "DS-0002", "package": "containers/example/Dockerfile",
        "current": "Specify at least 1 USER command in Dockerfile with non-root user as argument",
        "fixed": "", "severity": "high", "source": ss.MISCONFIG_SOURCE}]


def test_a_misconfig_flows_through_findings(tmp_path, monkeypatch):
    """The dedicated misconfig classifier is read by the same `findings()` gate as the scanners."""

    # Given a trivy report that also carries an IaC misconfiguration and a vuln advisory
    report = {"Results": [
        {"Class": "os-pkgs", "Vulnerabilities": [
            {"VulnerabilityID": "CVE-1", "PkgName": "numpy", "InstalledVersion": "1.0",
             "FixedVersion": "1.1", "Severity": "CRITICAL"}]},
        {"Target": "containers/example/Dockerfile", "Class": "config", "Type": "dockerfile",
         "Misconfigurations": TRIVY_MISCONFIG["Results"][0]["Misconfigurations"]},
    ]}
    monkeypatch.setattr(ss, "REPORTS", _reports(tmp_path, trivy=report))

    # When  every finding is read
    items = ss.findings()

    # Then  both the advisory and the IaC misconfiguration are present, in the fixed finding shape
    assert any(i["source"] == "trivy" and i["id"] == "CVE-1" for i in items)
    assert any(i["source"] == ss.MISCONFIG_SOURCE and i["id"] == "DS-0002" for i in items)


def test_a_critical_misconfig_blocks_even_with_require_fix(tmp_path, monkeypatch):
    """A HIGH IaC misconfiguration blocks — a misconfig is always actionable (edit the IaC, never
    wait for a patched version), so `require_fix` must not suppress it (issue #2234)."""

    # Given a HIGH misconfiguration in the report (no package, no fixed version)
    items = ss._trivy_misconfig_findings(TRIVY_MISCONFIG)

    # When  the full policy is applied
    bad = ss.blocking(items, POLICY, "full")

    # Then  it blocks even with `require_fix` on — a misconfiguration's fix is editing the file
    assert [i["id"] for i in bad] == ["DS-0002"]
    assert ss.blocking(items, dict(POLICY, require_fix=True), "full") != []


def test_a_medium_misconfig_is_recorded_never_blocking():
    """`fail_on` still gates an IaC misconfiguration: MEDIUM is recorded, never a red (issue
    #2234)."""

    # Given a MEDIUM misconfiguration
    items = ss._trivy_misconfig_findings(TRIVY_MISCONFIG_MEDIUM)

    # When  the full policy is applied
    bad = ss.blocking(items, POLICY, "full")

    # Then  it is not blocking (only critical/high gate), and the report-only PR mode is empty too
    assert bad == []
    assert ss.blocking(items, POLICY, "pr") == []


def test_grype_findings_are_normalised():
    """A grype match carries its fixed versions in `fix.versions`, not one string."""

    # Given a grype report
    # When  it is normalised
    items = ss._grype_findings(GRYPE_ONE)

    # Then  the fixed version is joined from the list
    assert items[0]["fixed"] == "3.1"
    assert items[0]["severity"] == "critical"


def test_full_mode_fails_on_a_high_with_a_fix(tmp_path, monkeypatch):
    """The scheduled/manual policy is critical+high with a fix available."""

    # Given a report with a HIGH that has a fix
    items = ss._trivy_findings(TRIVY_HIGH)

    # When  the full policy is applied
    bad = ss.blocking(items, POLICY, "full")

    # Then  it blocks
    assert [i["id"] for i in bad] == ["CVE-3"]


def test_pr_mode_only_fails_on_critical(tmp_path, monkeypatch):
    """A pre-existing High must not red every PR; the daily run still enforces it."""

    # Given a HIGH with a fix
    items = ss._trivy_findings(TRIVY_HIGH)

    # When  a pull-request policy that names critical only is applied
    bad = ss.blocking(items, POLICY, "pr")

    # Then  it does not block, and the full mode still does
    assert bad == []
    assert ss.blocking(items, POLICY, "full") != []


def test_the_shipped_pr_policy_is_report_only(tmp_path, monkeypatch):
    """The shipped policy does not gate a report-only run at all — it reports and files."""

    # Given this repository's policy
    pol = ss.policy()

    # Then  a report-only run is report-only, and a blocking critical still fails the full mode
    assert pol["pr_fail_on"] == []
    assert ss.blocking(ss._trivy_findings(TRIVY_OK), pol, "pr") == []
    assert ss.blocking(ss._trivy_findings(TRIVY_OK), pol, "full") != []


def test_an_event_outside_enforce_events_is_report_only(tmp_path, monkeypatch):
    """A push or a PR may never gate: the reports that failed run 40525155122 exit 0."""

    # Given the reports that failed run 40525155122 (one critical, two highs, all with a fix)
    items = ss._trivy_findings({"Results": [{"Vulnerabilities": [
        {"VulnerabilityID": "GHSA-6q48-6c7w-9gw2", "PkgName": "certifi",
         "InstalledVersion": "2026.7.22", "FixedVersion": "2026.10.18", "Severity": "CRITICAL"},
        {"VulnerabilityID": "CVE-2026-112940", "PkgName": "filelock",
         "InstalledVersion": "3.32.5", "FixedVersion": "4.2.1", "Severity": "HIGH"},
        {"VulnerabilityID": "CVE-2026-97687", "PkgName": "urllib3",
         "InstalledVersion": "2.7.0", "FixedVersion": "2.8.0", "Severity": "HIGH"},
    ]}]})
    pol = ss.policy()
    d = _reports(tmp_path, trivy={"Results": [{"Vulnerabilities": [
        {"VulnerabilityID": "GHSA-6q48-6c7w-9gw2", "PkgName": "certifi",
         "InstalledVersion": "2026.7.22", "FixedVersion": "2026.10.18", "Severity": "CRITICAL"},
        {"VulnerabilityID": "CVE-2026-112940", "PkgName": "filelock",
         "InstalledVersion": "3.32.5", "FixedVersion": "4.2.1", "Severity": "HIGH"},
        {"VulnerabilityID": "CVE-2026-97687", "PkgName": "urllib3",
         "InstalledVersion": "2.7.0", "FixedVersion": "2.8.0", "Severity": "HIGH"},
    ]}]})
    monkeypatch.setattr(ss, "REPORTS", d)

    # When  the verdict runs for a push and for a pull request
    # Then  both are report-only and exit 0, while the mode resolver still says they may not gate
    assert ss.verdict("", "push") == 0
    assert ss.verdict("", "pull_request") == 0
    assert ss.mode_for("push", pol) == "pr"
    assert items and len(items) == 3


def test_the_scheduled_run_still_gates(tmp_path, monkeypatch):
    """The daily run is where a fixable critical DOES fail — that is the gate."""

    # Given a report with a critical that has a fix
    monkeypatch.setattr(ss, "REPORTS", _reports(tmp_path, trivy=TRIVY_OK))

    # When  the verdict runs for the schedule
    # Then  it exits 1 under the shipped policy
    assert ss.mode_for("schedule") == "full"
    assert ss.verdict("", "schedule") == 1


def test_check_refuses_a_policy_that_gates_a_push(tmp_path, monkeypatch):
    """`enforce_events` may never name an event that carries main CI (#738)."""

    # Given a policy that would gate a push
    bad = {"fail_on": ["critical"], "pr_fail_on": [], "issue_severities": ["critical"],
           "enforce_events": ["push"]}
    path = tmp_path / "security-policy.json"
    path.write_text(ss.json.dumps(bad), encoding="utf-8")
    monkeypatch.setattr(ss, "POLICY", path)

    # When  the gate runs
    # Then  it fails
    assert ss.check() == 1


def test_check_refuses_an_empty_or_unknown_enforce_events(tmp_path, monkeypatch):
    """An empty list can never gate; an unknown event is a typo, not a policy."""

    # Given an empty list, then an unknown event
    for enforce in ([], ["scheduel"]):
        bad = {"fail_on": ["critical"], "pr_fail_on": [], "issue_severities": ["critical"],
               "enforce_events": enforce}
        path = tmp_path / f"policy-{len(enforce)}-{enforce[0] if enforce else 'none'}.json"
        path.write_text(ss.json.dumps(bad), encoding="utf-8")
        monkeypatch.setattr(ss, "POLICY", path)

        # When  the gate runs
        # Then  it fails
        assert ss.check() == 1, enforce


def test_the_scan_is_never_a_pr_or_push_check(tmp_path, monkeypatch):
    """A trigger the scan must never carry is refused by the gate that reads the workflow."""

    # Given a workflow with a `push:` and a `pull_request:` trigger
    workflow = tmp_path / "security-scan.yml"
    workflow.write_text("name: x\non:\n  push:\n    branches: [\"main\"]\n"
                        "  pull_request:\n    branches: [\"main\"]\n  schedule:\n"
                        "    - cron: \"5 4 * * *\"\n", encoding="utf-8")
    monkeypatch.setattr(ss, "WORKFLOW", workflow)

    # When  the gate runs
    # Then  it fails, and the triggers it read are the ones it complains about
    assert ss.triggers(workflow.read_text()) == {"push", "pull_request", "schedule"}
    assert ss.check() == 1


def test_the_scanner_runs_as_the_invoking_user(tmp_path, monkeypatch):
    """The mounted checkout belongs to the runner user; the scanner must write its report as them."""

    # Given a docker stub that records its argv
    log = _docker_stub(tmp_path, monkeypatch, pull_ok=True, inspect_ok=True)

    # When  a scan is launched
    ss._run(["version"], ss.image_ref("trivy"))

    # Then  `--user <uid>:<gid>` is on the command line (issues #433 and the CI permission denial)
    runs = [json.loads(l) for l in log.read_text().splitlines() if json.loads(l)[0] == "run"]
    assert len(runs) == 1
    argv = runs[0]
    assert "--user" in argv
    assert argv[argv.index("--user") + 1] == f"{os.getuid()}:{os.getgid()}"


def test_a_finding_without_a_fix_never_blocks():
    """`require_fix` is why an unfixable advisory cannot stall the repository."""

    # Given a CRITICAL with no fixed version
    items = ss._trivy_findings(TRIVY_NO_FIX)

    # When  the policy requires a fix
    bad = ss.blocking(items, POLICY, "full")

    # Then  it is recorded but not blocking
    assert bad == []
    assert ss.blocking(items, dict(POLICY, require_fix=False), "full") != []


def test_verdict_fails_and_passes_from_the_reports(tmp_path, monkeypatch):
    """`make security-verdict` is the run's exit code, driven only by the reports on disk."""

    # Given a reports directory with a blocking finding
    monkeypatch.setattr(ss, "REPORTS", _reports(tmp_path, trivy=TRIVY_OK))

    # When  the verdict runs
    rc_bad = ss.verdict("full")

    # Then  it fails, and an empty directory passes with nothing recorded
    assert rc_bad == 1
    monkeypatch.setattr(ss, "REPORTS", _reports(tmp_path / "empty", trivy={"Results": []}))
    assert ss.verdict("full") == 0


def test_an_unparseable_report_is_not_a_pass(tmp_path, monkeypatch):
    """A truncated report must fail loudly; treating it as clean is the defect this prevents."""

    # Given a corrupt trivy report
    d = tmp_path / "reports"
    d.mkdir()
    (d / "trivy.json").write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(ss, "REPORTS", d)

    # When  findings are read
    try:
        ss.findings()
    except SystemExit as exc:
        # Then  the run refuses rather than reporting zero findings
        assert "does not parse" in str(exc)
    else:
        raise AssertionError("a corrupt report was treated as clean")


def test_the_policy_and_digests_are_sane():
    """The real tree: a non-empty policy, pr_fail_on ⊆ fail_on, every scanner ref recorded."""

    # Given this repository
    # When  the gate runs
    rc = ss.check()

    # Then  it passes
    assert rc == 0


def test_the_workflow_uses_the_digests_and_a_manual_form():
    """The workflow must name the pinned refs, keep the manual trigger, and never install a scanner."""

    # Given the scan workflow
    text = (REPO / ".github/workflows/security-scan.yml").read_text(encoding="utf-8")

    # When  it is read for the pipeline's hard requirements
    # Then  the manual trigger, the guard, the make seam and the pinned upload actions are present
    assert "workflow_dispatch:" in text
    assert "  schedule:" in text
    assert "make security-scan-all" in text and "make security-verdict" in text
    assert "guard:" in text
    # And   it is its OWN pipeline: no pull_request and no push trigger may gate it (issue #738)
    assert "  pull_request:" not in text
    assert "  push:" not in text
    # And nothing floats: every `uses:` is a 40-hex SHA
    import re
    refs = re.findall(r"uses:\s+(\S+)", text)
    assert refs, "the workflow uses no action at all"
    assert all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", ref) for ref in refs), refs


def _manifest_json(index: str, child: str) -> str:
    """What `docker buildx imagetools inspect --format {{json .Manifest}}` prints: the index
    digest plus the per-platform children the host actually runs (issue #2609)."""
    return json.dumps({
        "mediaType": "application/vnd.oci.image.index.v1+json",
        "digest": index,
        "manifests": [{"digest": child,
                       "mediaType": "application/vnd.oci.image.manifest.v1+json",
                       "platform": {"architecture": "amd64", "os": "linux"}}],
    })


def _digest_pair(tool: str, index: str | None = None) -> dict:
    """A manifest/index pair consistent with `digests.json`'s pinned digest for `tool` — or,
    with an explicit `index`, one for a tag whose published image has moved off the record."""
    recorded = str(ss.digests()[tool]["image_digest"])
    index = index or recorded
    child = "sha256:" + "".join(reversed(index[7:]))  # deterministic synthetic child manifest
    return {"manifest": _manifest_json(index, child), "child": child, "recorded": recorded}


def _docker_stub(tmp_path: Path, monkeypatch, *, pull_ok: bool, build_ok: bool = True,
                 inspect_ok: bool = False, image: dict | None = None) -> Path:
    """A real executable standing in for `docker`, so which branch the code takes is observable.
    `buildx inspect` answers with a manifest index consistent with `digests.json` (issue #2609:
    `ensure_image` verifies the executed digest); `image` overrides one tool with
    `{"manifest": ..., "id": ...}` — the id makes the LOCAL copy report that image id, which is
    how a stale-copy or moved-tag scenario is constructed."""
    log = tmp_path / "docker.log"
    stub = tmp_path / "docker"
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "open(os.environ['DOCKER_STUB_LOG'], 'a').write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "which = sys.argv[1]\n"
        "ok = os.environ.get('DOCKER_STUB_' + which.upper(), '0') == '1'\n"
        "man = json.loads(os.environ.get('DOCKER_STUB_MANIFESTS', '{}'))\n"
        "ref = next((a for a in sys.argv if a.startswith('ghcr.io/')), '')\n"
        "tool = ref.rsplit('/', 1)[-1].split(':')[0]\n"
        "rec = man.get(tool) or {}\n"
        "if which == 'buildx' and rec.get('manifest'):\n"
        "    sys.stdout.write(rec['manifest'])\n"
        "if which == 'image' and rec.get('id'):\n"
        "    sys.stdout.write(rec['id'] + '\\n')\n"
        "sys.exit(0 if ok else 1)\n",
        encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("DOCKER_STUB_LOG", str(log))
    monkeypatch.setenv("DOCKER_STUB_INSPECT", "1" if inspect_ok else "0")
    monkeypatch.setenv("DOCKER_STUB_PULL", "1" if pull_ok else "0")
    monkeypatch.setenv("DOCKER_STUB_BUILD", "1" if build_ok else "0")
    monkeypatch.setenv("DOCKER_STUB_BUILDX", "1")
    pinned = {t: {"manifest": _digest_pair(t)["manifest"]} for t in ss.TOOLS}
    for tool, spec in (image or {}).items():
        pinned[tool] = dict(spec)
        if spec.get("id"):
            monkeypatch.setenv("DOCKER_STUB_IMAGE", "1")
    monkeypatch.setenv("DOCKER_STUB_MANIFESTS", json.dumps(pinned))
    monkeypatch.setattr(ss, "RUNTIME", str(stub))
    # The deferral build now runs through the shared seam (scanner_image.build, issue #744), whose
    # own RUNTIME the stub must also answer — one build path, one stub.
    monkeypatch.setattr(ss._scanner_image, "RUNTIME", str(stub))
    return log


def test_a_published_image_is_pulled_and_used(tmp_path, monkeypatch):
    """The normal path: the ref is inspectable, so nothing is built."""

    # Given a docker whose inspect and pull succeed
    log = _docker_stub(tmp_path, monkeypatch, pull_ok=True, inspect_ok=True)

    # When  the image is resolved
    ref = ss.ensure_image("trivy")

    # Then  the ref is the digests file's and no build ran
    assert ref == ss.image_ref("trivy")
    assert not [l for l in log.read_text().splitlines() if '"build"' in l]


def test_a_pull_miss_delegates_the_build_to_scanner_image_build(tmp_path, monkeypatch):
    """Before the first publish (and on a fork run) the image is obtained through the ONE builder:
    `security_scan.ensure_image` stops carrying its own `docker build` and delegates to
    `scanner_image.build` for that scanner (issue #745 item 4 — a deferral NEVER pushes, so it
    calls the builder, not `ensure`).
    """

    # Given a docker whose pull fails, so the scan must get the image another way
    log = _docker_stub(tmp_path, monkeypatch, pull_ok=False)
    # ... and a recorder standing in for the ONE builder it must delegate to
    calls: list[tuple[str, str]] = []

    class _BuildRecorder:
        @staticmethod
        def build(scanner: str, tag: str | None = None) -> str:
            calls.append((scanner, tag or ""))
            return tag or ""

    monkeypatch.setattr(ss, "_scanner_image", _BuildRecorder)

    # When  the image is resolved
    ref = ss.ensure_image("trivy")

    # Then  it returned the digests ref and delegated to scanner_image.build for that scanner,
    #       tagging it with the exact ref the scan asked for, and hand-rolled no `docker build`
    #       of its own (the delegation is the ONE code path)
    assert ref == ss.image_ref("trivy")
    assert calls == [("trivy", ss.image_ref("trivy"))]
    assert not [l for l in log.read_text().splitlines() if '"build"' in l]


def test_a_build_failure_is_loud(tmp_path, monkeypatch):
    """A scanner that cannot be obtained at all fails the run; it is never a silent skip."""

    # Given a docker whose pull fails, and a builder that cannot build the image either
    _docker_stub(tmp_path, monkeypatch, pull_ok=False)

    class _FailingBuilder:
        @staticmethod
        def build(scanner: str, tag: str | None = None) -> str:
            raise SystemExit(f"[scanner-image] build failed: {scanner}")

    monkeypatch.setattr(ss, "_scanner_image", _FailingBuilder)

    # When  the image is resolved
    try:
        ss.ensure_image("trivy")
    except SystemExit as exc:
        # Then  the run refuses, naming the scanner
        assert "build failed: trivy" in str(exc)
    else:
        raise AssertionError("a scanner that could not be obtained was accepted")


# --- the executed image digest is verified (issue #2609) ---


def test_every_scanner_digest_entry_carries_an_image_digest():
    """The real tree: every scanner entry pins the published image's manifest digest, so a scan
    can prove WHICH bytes it ran — not just which tag it asked for."""

    # Given this repository
    # When  the scan module reads its pinned scanner records
    for tool in ss.TOOLS:
        digest = str(ss.digests()[tool].get("image_digest") or "")

        # Then  each carries a manifest digest in sha256:<64 hex> form
        assert ss.DIGEST_RE.fullmatch(digest), (tool, digest)


def test_a_scan_names_the_executed_image_digest(tmp_path, monkeypatch, capsys):
    """Every resolved image prints the digest it will actually run (issue #2609 criterion 2)."""

    # Given a registry that answers with the pinned image's manifest
    _docker_stub(tmp_path, monkeypatch, pull_ok=True)
    recorded = _digest_pair("trivy")["recorded"]

    # When  the image is resolved
    ss.ensure_image("trivy")

    # Then  the run names that digest
    assert recorded in capsys.readouterr().out


def test_a_moved_tag_stops_the_scan(tmp_path, monkeypatch):
    """A tag that has been re-pushed under a different digest is the exact drift issue #2609
    measured live (semgrep:5954e2aad609 served two different digests): the scan refuses, naming
    both digests."""

    # Given a local copy from the pinned build and a registry whose tag now serves a new digest
    recorded_pair = _digest_pair("trivy")
    moved = _digest_pair("trivy", index="sha256:" + "e" * 64)
    _docker_stub(tmp_path, monkeypatch, pull_ok=True,
                 image={"trivy": {"manifest": moved["manifest"], "id": recorded_pair["child"]}})

    # When  the image is resolved
    try:
        ss.ensure_image("trivy")
    except SystemExit as exc:
        # Then  it refuses, naming the registry's new digest AND the pinned record it no longer
        # matches — the exact drift issue #2609 measured live
        message = str(exc)
        assert "the tag moved" in message
        assert "sha256:" + "e" * 64 in message
        assert recorded_pair["recorded"] in message
    else:
        raise AssertionError("a scanner image that differs from the pinned digest was accepted")


def test_a_stale_local_copy_is_refused(tmp_path, monkeypatch):
    """`docker run <ref>` picks whatever the daemon last pulled under that tag. If that copy is
    not the pinned image, the scan must say so instead of scanning on the stale bytes."""

    # Given a registry that answers with the pinned manifest but a local copy with a foreign id
    pinned = _digest_pair("trivy")
    _docker_stub(tmp_path, monkeypatch, pull_ok=True,
                 image={"trivy": {"manifest": pinned["manifest"], "id": "sha256:" + "f" * 64}})

    # When  the image is resolved
    try:
        ss.ensure_image("trivy")
    except SystemExit as exc:
        # Then  the stale copy is named, together with the digest it should have had
        message = str(exc)
        assert "stale local scanner" in message
        assert "sha256:" + "f" * 64 in message
        assert pinned["recorded"] in message
    else:
        raise AssertionError("a stale local scanner copy was accepted")


def test_the_deferred_build_names_its_digest(tmp_path, monkeypatch, capsys):
    """A fork run builds the deferral locally; the digest it prints is the pinned one, from the
    built manifest — not a claim about a registry it cannot read."""

    # Given no registry access (pull fails, local build succeeds)
    _docker_stub(tmp_path, monkeypatch, pull_ok=False, build_ok=True)
    recorded = _digest_pair("trivy")["recorded"]

    # When  the image is resolved
    ss.ensure_image("trivy")

    # Then  the built locally, at the recorded digest
    out = capsys.readouterr().out
    assert "built locally" in out
    assert recorded in out


def test_a_digest_entry_without_image_digest_refuses_to_run(tmp_path, monkeypatch):
    """A record missing the image pin cannot certify anything: the scan refuses to launch."""

    # Given the stub first (it needs the real digests), then a record stripped of image_digest
    _docker_stub(tmp_path, monkeypatch, pull_ok=True)
    original = ss.digests()
    monkeypatch.setattr(ss, "digests", lambda: {
        tool: {k: v for k, v in entry.items() if k != "image_digest"}
        for tool, entry in original.items()})

    # When  the image is resolved
    try:
        ss.ensure_image("trivy")
    except SystemExit as exc:
        # Then  the refusal names the missing field and the command that fills it
        assert "image_digest" in str(exc)
    else:
        raise AssertionError("a scanner record without an image digest was accepted")


def test_semgrep_uses_the_committed_content_addressed_pack(tmp_path, monkeypatch):
    """Semgrep runs the COMMITTED, content-pinned rules pack, not a floating registry alias, and
    keeps metrics off (issue #1284): `--config <repo>/rules/default.yml` — the same immutable rule
    set for the same tree, with no registry fetch at scan time."""

    # Given a docker stub that records the argv
    log = _docker_stub(tmp_path, monkeypatch, pull_ok=True, inspect_ok=True)

    # When  a semgrep scan is launched
    ss.scan("semgrep")

    # Then  the argv names the committed pack file (not `p/default`, not `auto`) and keeps metrics off
    runs = [json.loads(l) for l in log.read_text().splitlines() if json.loads(l)[0] == "run"]
    argv = runs[-1]
    flag = argv[argv.index("--config") + 1]
    assert flag.endswith("containers/scanners/semgrep/rules/default.yml"), flag
    assert "p/default" not in argv and "auto" not in argv
    assert "--metrics" in argv and "off" in argv


def test_semgrep_scan_excludes_the_report_directory(tmp_path, monkeypatch):
    """The scan must not scan its own output: `security-reports/` is excluded from the semgrep run,
    or the second of two scans at the same tree sha reports `paths.scanned` with one more entry
    (issue #1284's byte-identical criterion; measured in the review of PR #2082). The committed rule
    pack is excluded too (issue #2105): the pack lives inside the scan root and its own bytes are
    detector patterns, so scanning them reports a self-finding whose only "fix" would weaken the
    scanner — the exclusion removes the self-reference and nothing else."""

    # Given a docker stub that records the argv
    log = _docker_stub(tmp_path, monkeypatch, pull_ok=True, inspect_ok=True)

    # When  a semgrep scan is launched
    ss.scan("semgrep")

    # Then  the argv excludes the report directory it writes into AND its own rule pack
    runs = [json.loads(l) for l in log.read_text().splitlines() if json.loads(l)[0] == "run"]
    argv = runs[-1]
    pair = [argv[i + 1] for i, a in enumerate(argv) if a == "--exclude"]
    assert "security-reports" in pair, argv
    assert "containers/scanners/semgrep/rules" in pair, argv


def test_semgrep_strips_wallclock_so_output_is_reproducible(tmp_path, monkeypatch):
    """Two scans of the same tree / pack must be byte-identical (issue #1284): the `time` and
    `profiling_results` wall-clock blocks semgrep embeds every run are removed from semgrep.json."""

    # Given a report with a timing block that differs between runs
    report = tmp_path / "reports"
    report.mkdir()
    out = report / "semgrep.json"
    out.write_text(json.dumps({"results": [{"rule": "x"}], "time": {"total_time": 1.0},
                               "profiling_results": [{"x": 2.0}]}), encoding="utf-8")
    monkeypatch.setattr(ss, "REPORTS", report)

    # When  the timing is stripped
    ss._strip_semgrep_timing(out)

    # Then  the report has no wall-clock and the findings/structure are unchanged
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "time" not in data and "profiling_results" not in data
    assert data["results"] == [{"rule": "x"}]


def test_semgrep_rule_pack_is_not_itself_a_credential_shape():
    """The committed semgrep pack is a set of DETECTION rules, so its own bytes must not look like
    the credential it detects (issue #1284, measured on PR #2082): `make secret-scan` red at
    `containers/scanners/semgrep/rules/default.yml:1465` with gitleaks' `private-key` rule, which
    reads any `-----BEGIN … PRIVATE KEY-----` header in a committable file as a leaked key. Each
    header writes the `KEY` with a YAML `\\x59` escape, so the pattern semgrep LOADS is unchanged
    while the file's bytes carry no header.
    """

    import yaml

    # Given the committed pack, parsed the way semgrep parses it
    raw = (REPO / "containers" / "scanners" / "semgrep" / "rules" / "default.yml").read_text(
        encoding="utf-8")
    rules = yaml.safe_load(raw)

    # Then  no PEM private-key header is present in the file's bytes (that shape is the finding)
    assert not re.search(r"-----BEGIN[ A-Z0-9_-]{0,100}PRIVATE KEY( BLOCK)?-----", raw)

    # And   the escape resolved: a loaded rule still names a key header, so the pack still detects
    #       one, and no loaded string kept a literal escape (which would silently neuter the rule)
    def strings(node):
        if isinstance(node, dict):
            for value in node.values():
                yield from strings(value)
        elif isinstance(node, list):
            for value in node:
                yield from strings(value)
        elif isinstance(node, str):
            yield node

    loaded = list(strings(rules))
    assert any("PRIVATE KEY-----" in s for s in loaded), "no loaded rule names a private-key header"
    assert not any("\\x59" in s for s in loaded), "an escape is unresolved in the loaded rule set"


def test_check_fails_when_digests_omits_the_semgrep_rules_sha(tmp_path, monkeypatch):
    """A scan whose SAST rule set is not content-pinned cannot be trusted (issue #1284):
    `make check-security-scan` fails when digests.json's semgrep entry has no `rules_sha`."""

    # Given a digests.json without the semgrep rules_sha the committed pack requires
    recorded = json.loads(ss.DIGESTS.read_text(encoding="utf-8"))
    recorded["semgrep"] = {k: v for k, v in recorded["semgrep"].items() if k != "rules_sha"}
    fake = tmp_path / "digests.json"
    fake.write_text(json.dumps(recorded), encoding="utf-8")
    monkeypatch.setattr(ss, "DIGESTS", fake)

    # When  the gate runs, it must fail naming the missing content-pin
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = ss.check()
    assert rc == 1
    assert "rules_sha" in buf.getvalue()


def test_check_fails_when_a_scanner_version_lags_the_declared_baseline(tmp_path, monkeypatch):
    """A pinned engine that silently lags the declared current-release baseline is a freshness
    finding (issue #1284): the gate fails until the Dockerfile + make scanner-digests catch up."""

    # Given a digests.json with an older semgrep than the declared baseline
    recorded = json.loads(ss.DIGESTS.read_text(encoding="utf-8"))
    recorded["semgrep"]["version"] = "0.9.0-r0"
    fake = tmp_path / "digests.json"
    fake.write_text(json.dumps(recorded), encoding="utf-8")
    monkeypatch.setattr(ss, "DIGESTS", fake)

    # When  the gate runs
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = ss.check()
    # Then  it fails naming the lagging engine and the baseline
    assert rc == 1
    assert "semgrep" in buf.getvalue() and "baseline" in buf.getvalue()


def test_check_fails_when_the_baked_sbom_tool_lags_its_baseline(tmp_path, monkeypatch):
    """The SBOM tool rides the grype image, so its freshness record lives there too (issue #2708):
    `grype.syft_version` older than `SCANNER_BASELINE["syft"]` (or absent) reds the gate — a
    lagging cataloger silently narrows what the SBOM contains, so grype never matches it."""

    # Given a digests.json whose baked syft lags the declared baseline
    recorded = json.loads(ss.DIGESTS.read_text(encoding="utf-8"))
    assert recorded["grype"].get("syft_version"), "digests.json must carry the baked syft record"
    recorded["grype"]["syft_version"] = "1.50.0-r0"
    fake = tmp_path / "digests.json"
    fake.write_text(json.dumps(recorded), encoding="utf-8")
    monkeypatch.setattr(ss, "DIGESTS", fake)

    # When  the gate runs
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = ss.check()

    # Then  it fails naming the lagging tool and the baseline it lags
    assert rc == 1
    assert "syft" in buf.getvalue() and "baseline" in buf.getvalue()


def test_check_fails_when_the_sbom_tool_has_no_freshness_record(tmp_path, monkeypatch):
    """A tool with no record cannot be checked at all (issue #2708): dropping `syft_version`
    from the grype entry reds the gate naming the missing record."""

    # Given a digests.json whose grype entry dropped the baked syft record
    recorded = json.loads(ss.DIGESTS.read_text(encoding="utf-8"))
    recorded["grype"] = {k: v for k, v in recorded["grype"].items() if k != "syft_version"}
    fake = tmp_path / "digests.json"
    fake.write_text(json.dumps(recorded), encoding="utf-8")
    monkeypatch.setattr(ss, "DIGESTS", fake)

    # When  the gate runs
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = ss.check()

    # Then  it fails naming the missing freshness record
    assert rc == 1
    assert "syft_version" in buf.getvalue()


def test_committed_syft_record_sits_on_the_declared_baseline():
    """The committed record passes the same freshness gate it enforces (issue #2708):
    digests.json `grype.syft_version` equals `SCANNER_BASELINE["syft"]` and the grype Dockerfile
    bakes that exact version."""

    recorded = json.loads(ss.DIGESTS.read_text(encoding="utf-8"))
    baseline = ss.SCANNER_BASELINE.get("syft")
    assert baseline, "SCANNER_BASELINE must carry a syft entry (issue #2708)"
    assert recorded["grype"].get("syft_version") == baseline
    dockerfile = (Path(__file__).resolve().parent.parent
                  / "containers" / "scanners" / "grype" / "Dockerfile")
    text = dockerfile.read_text(encoding="utf-8")
    assert f"ARG SYFT_VERSION={baseline}" in text, (
        "the grype Dockerfile must bake the baseline version it declares")


def test_check_reds_a_pin_older_than_the_rules_recency_baseline(tmp_path, monkeypatch):
    """Negative control (issue #2283): a committed rules pack whose rules_captured_at is older than
    the recency baseline must RED `make check-security-scan` — a frozen rule set must not pass green
    while upstream adds rules it never sees."""

    # Given a digests.json whose committed pack is many days old (older than RULES_BASELINE_DAYS)
    recorded = json.loads(ss.DIGESTS.read_text(encoding="utf-8"))
    recorded["semgrep"]["rules_captured_at"] = "2020-01-01"
    fake = tmp_path / "digests.json"
    fake.write_text(json.dumps(recorded), encoding="utf-8")
    monkeypatch.setattr(ss, "DIGESTS", fake)

    # When  the gate runs
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = ss.check()

    # Then  it fails naming the stale pack and the recency baseline
    assert rc == 1
    out = buf.getvalue()
    assert "rules_captured_at" in out and "2020-01-01" in out
    assert str(ss.RULES_BASELINE_DAYS) in out


def test_check_reds_a_pin_with_no_rules_count(tmp_path, monkeypatch):
    """The rules recency floor needs a parity target (issue #2283): a digests.json with no
    rules_count cannot claim the committed pack is compared against upstream p/default."""

    recorded = json.loads(ss.DIGESTS.read_text(encoding="utf-8"))
    recorded["semgrep"] = {k: v for k, v in recorded["semgrep"].items() if k != "rules_count"}
    fake = tmp_path / "digests.json"
    fake.write_text(json.dumps(recorded), encoding="utf-8")
    monkeypatch.setattr(ss, "DIGESTS", fake)

    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = ss.check()
    assert rc == 1
    assert "rules_count" in buf.getvalue()


def test_check_green_when_pack_within_recency_baseline(tmp_path, monkeypatch):
    """The committed pack is within the recency floor (issue #2283): the current digests.json
    records a recent rules_captured_at, so the gate stays green without a stale-pack red."""

    recorded = json.loads(ss.DIGESTS.read_text(encoding="utf-8"))
    captured = recorded["semgrep"].get("rules_captured_at")
    assert captured, "digests.json must record rules_captured_at for the freshness floor"
    fake = tmp_path / "digests.json"
    fake.write_text(json.dumps(recorded), encoding="utf-8")
    monkeypatch.setattr(ss, "DIGESTS", fake)

    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = ss.check()
    # The only reds we tolerate here are the ones that pre-date this check (no policy empty etc.)
    out = buf.getvalue()
    assert "rules_captured_at" not in out, out


def test_the_stack_needs_no_account_and_no_secret(tmp_path, monkeypatch):
    """The whole stack is local: Trivy, Syft, Grype and Semgrep run from pinned images, and no
    scanner is behind a token — so no run is ever skipped for a missing credential."""

    # Given the shipped tool set
    # Then  every tool is one of the local scanners, and there is no opt-in SaaS set
    assert ss.TOOLS == ("trivy", "grype", "semgrep"), ss.TOOLS
    assert ss.ALL_TOOLS == ("syft",) + ss.TOOLS
    assert not hasattr(ss, "OPTIONAL_TOOLS")

    # And   the whole stack's images are recorded by digest-verified entries
    assert set(ss.digests()) == {"trivy", "grype", "semgrep"}

    # And   Syft is reachable as a tool id (it writes the SBOM the Grype match reads)
    monkeypatch.setattr(ss, "ensure_image_for", lambda ref: ref)
    calls = []
    monkeypatch.setattr(ss.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or type("R", (), {"returncode": 0})())
    assert ss.scan("syft") == 0
    assert "--entrypoint" in calls[-1] and calls[-1][calls[-1].index("--entrypoint") + 1] == "syft"


def test_an_unknown_tool_is_refused():
    """An unknown tool id fails by name instead of silently scanning nothing."""

    # Given an id that is not in the stack
    # When  a scan is asked for it
    try:
        ss.scan("gitleaks")
    except SystemExit as exc:
        # Then  it exits non-zero naming what IS known, and never runs a scanner
        assert "unknown tool" in str(exc) and "grype" in str(exc), str(exc)
    else:
        raise AssertionError("an unknown tool was accepted")


# ---------------------------------------------------------------------------
# Live freshness (issue #2709): pins are compared against what the Wolfi x86_64 index publishes
# TODAY, not against the frozen SCANNER_BASELINE dict. Hermetic: every test below calls the pure
# `_evaluate_freshness`/`_index_from_snapshot` seam with fixture text and cannot be traced to the
# fetch (issue #1067). The dispatcher's live reach sits behind `@pytest.mark.network` tests.
# ---------------------------------------------------------------------------

FRESHNESS_PINS = {"trivy": "0.70.0-r5", "grype": "0.121.2-r1", "semgrep": "1.165.0-r0",
                  "syft": "1.57.0-r1"}


def _stanza(name: str, version: str, age_days: int) -> str:
    """One APKINDEX stanza for `name` built `age_days` ago."""
    epoch = int(time.time() - age_days * 86400)
    return (f"C:Q1234=\nP:{name}\nV:{version}\nA:x86_64\nT:\nS:1\nI:1\nO:1\nc:abc123\n"
            f"d:dep\nF:\nn:{name}\nt:{epoch} 1000")


def _freshness_env(tmp_path, monkeypatch, index_text: str) -> None:
    """Point the comparison at fixture digests, a fixture Grype Dockerfile and a local index."""
    digests = {tool: {"version": ver, "tag": ver, "ref": f"img:{ver}",
                      "image_digest": "sha256:" + "0" * 64}
               for tool, ver in FRESHNESS_PINS.items() if tool != "syft"}
    monkeypatch.setattr(ss, "digests", lambda: digests)
    repo = tmp_path / "repo"
    (repo / "containers" / "scanners" / "grype").mkdir(parents=True)
    (repo / "containers" / "scanners" / "grype" / "Dockerfile").write_text(
        f"FROM wolfi-os\nARG SYFT_VERSION={FRESHNESS_PINS['syft']}\n", encoding="utf-8")
    monkeypatch.setattr(ss, "REPO", repo)
    snapshot = tmp_path / "APKINDEX"
    snapshot.write_text(index_text, encoding="utf-8")
    monkeypatch.setenv("WOLFI_APKINDEX", str(snapshot))


def test_the_grace_window_is_declared_and_pinned_by_a_test(tmp_path):
    """The grace is a named constant with a value a reader can defend (issue #2709)."""

    # Given  the live comparison's published knobs
    # When   a test reads them
    # Then   the grace is 7 days and the index is Wolfi's official x86_64 one
    assert ss.FRESHNESS_GRACE_DAYS == 7
    assert ss.WOLFI_INDEX_URL.startswith("https://packages.wolfi.dev/os/x86_64/")
    assert "syft" in ss.FRESHNESS_PACKAGES  # syft is compared even though it has no image entry


def test_fresh_pins_pass_and_name_the_index_they_measured(tmp_path, monkeypatch, capsys):
    """Every pin equals the newest published build: green, printing the index source."""

    # Given an index whose newest build per package equals each pin
    index = "\n\n".join(_stanza(t, v, 1) for t, v in FRESHNESS_PINS.items())
    _freshness_env(tmp_path, monkeypatch, index)

    # When  the live comparison runs on the pure evaluation seam
    rc = ss._evaluate_freshness(index, "committed fixture")
    out = capsys.readouterr().out

    # Then  it passes and prints the source it measured against
    assert rc == 0, out
    assert "measured against committed fixture" in out and "OK" in out


def test_a_pin_lagging_past_the_grace_window_fails_naming_the_delta(tmp_path, monkeypatch, capsys):
    """A lag that predates the grace window is a failure, naming package/pin/live-newest."""

    # Given grype and syft have published newer builds 30 days ago while the pins lag
    index = "\n\n".join([
        _stanza("trivy", "0.70.0-r5", 1),
        _stanza("semgrep", "1.165.0-r0", 1),
        _stanza("grype", "0.121.2-r1", 1),
        _stanza("grype", "0.121.3-r2", 30),
        _stanza("syft", "1.57.0-r1", 1),
        _stanza("syft", "1.57.1-r2", 30),
    ])
    _freshness_env(tmp_path, monkeypatch, index)

    # When  the live comparison runs on the pure evaluation seam
    rc = ss._evaluate_freshness(index, "committed fixture")
    out = capsys.readouterr().out

    # Then  it fails, and each delta names package, pinned version and the live newest
    assert rc == 1, out
    assert "grype: pinned 0.121.2-r1 but Wolfi published 0.121.3-r2" in out
    assert "syft: pinned 1.57.0-r1 but Wolfi published 1.57.1-r2" in out


def test_a_lag_inside_the_grace_window_passes_and_is_reported(tmp_path, monkeypatch, capsys):
    """Wolfi republishes faster than the repo chases: a fresh lag is printed, not red."""

    # Given grype's newer build was published 2 days ago (inside the 7d grace)
    index = "\n\n".join([
        _stanza("trivy", "0.70.0-r5", 1),
        _stanza("semgrep", "1.165.0-r0", 1),
        _stanza("grype", "0.121.2-r1", 1),
        _stanza("grype", "0.121.3-r2", 2),
        _stanza("syft", "1.57.0-r1", 1),
    ])
    _freshness_env(tmp_path, monkeypatch, index)

    # When  the live comparison runs on the pure evaluation seam
    rc = ss._evaluate_freshness(index, "committed fixture")
    out = capsys.readouterr().out

    # Then  the run passes and the lag is visible in the output
    assert rc == 0, out
    assert "grype: pinned 0.121.2-r1 lags 0.121.3-r2" in out and "grace" in out


def test_a_pinned_package_absent_from_the_index_fails_loudly(tmp_path, monkeypatch, capsys):
    """An unresolvable pin is never a silent pass."""

    # Given the index carries no grype package at all
    index = "\n\n".join([_stanza(t, v, 1) for t, v in FRESHNESS_PINS.items() if t != "grype"])
    _freshness_env(tmp_path, monkeypatch, index)

    # When  the live comparison runs on the pure evaluation seam
    rc = ss._evaluate_freshness(index, "committed fixture")
    out = capsys.readouterr().out

    # Then  it fails naming the package and the reason
    assert rc == 1, out
    assert "grype" in out and "never a silent pass" in out


def test_an_unreadable_index_snapshot_is_not_a_verdict(tmp_path):
    """A named-but-missing snapshot file is a loud failure, never a green by default."""

    # Given a snapshot path that does not exist
    missing = tmp_path / "APKINDEX.missing"

    # When  the snapshot seam is asked for it
    # Then  it refuses (SystemExit) rather than passing
    with pytest.raises(SystemExit) as got:
        ss._index_from_snapshot(missing)
    assert "does not exist" in str(got.value)


@pytest.mark.network
def test_scanner_freshness_prefers_the_named_snapshot_and_never_fetches(tmp_path, monkeypatch,
                                                                         capsys):
    """The CLI dispatcher honours `WOLFI_APKINDEX`: with a snapshot present the comparison runs
    with no network at all. Marked `network` because the dispatcher's code graph contains the
    live fetch (issue #1067), even though this test never reaches it."""

    # Given a named snapshot whose builds match every pin
    index = "\n\n".join(_stanza(t, v, 1) for t, v in FRESHNESS_PINS.items())
    _freshness_env(tmp_path, monkeypatch, index)  # sets WOLFI_APKINDEX to a written snapshot

    # When  the CLI dispatcher runs
    rc = ss.scanner_freshness()
    out = capsys.readouterr().out

    # Then  it measured against the snapshot, not the wire
    assert rc == 0, out
    assert "measured against local snapshot" in out


@pytest.mark.network
def test_the_live_wolfi_index_carries_every_compared_package():
    """One real fetch proves the live lane is grounded: the index parses and carries every
    package the comparison pins against. No verdict is asserted — pins may legitimately lag."""

    # Given Wolfi's live x86_64 index, fetched once
    text = ss._fetch_wolfi_index()

    # When  it is parsed with the same parser the gate uses
    index = ss._wolfi_stanzas(text)

    # Then  every compared package resolves to at least one dated build
    for package in ss.FRESHNESS_PACKAGES:
        assert index.get(package), f"live Wolfi index carries no `{package}` package"
        _, epoch = max(index[package], key=lambda b: b[0])
        assert epoch, f"live build for {package} carries no publish timestamp"


def test_the_offline_check_gate_stays_network_free(tmp_path):
    """`check` is hermetic: the live Wolfi fetch lives ONLY in the freshness step (issue #2709)."""

    # Given the shipped script source
    source = (REPO / "scripts" / "security_scan.py").read_text(encoding="utf-8")
    start = source.index("def check() -> int:")
    end = source.index("def main(argv")
    check_body = source[start:end]

    # When  the offline check's body is read
    # Then  it contains no Wolfi fetch and no freshness call
    assert "wolfi" not in check_body.lower()
    assert "urlopen" not in check_body and "scanner_freshness" not in check_body


def test_the_scan_lane_wires_the_live_comparison_after_the_scans_never_before_the_uploads(tmp_path):
    """security-scan.yml runs the comparison, captures it, and raises it only as the LAST step."""

    # Given the lane's workflow and the Makefile seam
    workflow = (REPO / ".github" / "workflows" / "security-scan.yml").read_text(encoding="utf-8")
    mk = (REPO / "mk" / "security.mk").read_text(encoding="utf-8")

    # When  they are read
    # Then  the step exists with an id and capture, the last step raises its outcome too,
    #       and the Makefile routes it through the script
    assert "id: freshness" in workflow and "continue-on-error: true" in workflow
    assert "run: make scanner-freshness" in workflow
    assert "steps.freshness.outcome == 'failure'" in workflow
    assert "python3 scripts/security_scan.py freshness" in mk
# Published-image scans (issue #2706): the runtime package set the product SHIPS
# ---------------------------------------------------------------------------

IMAGE_REF = "ghcr.io/asimov-agent/llgenie/llama-cpp:deadbeef-cuda@sha256:" + "ab" * 32


def test_an_image_scan_target_without_a_digest_is_refused(monkeypatch):
    """A target named only by a tag is refused: a scan must be able to name the manifest it judged
    (issue #2609's rule, turned onto the scan target — issue #2706)."""

    # Given a recorder standing in for the container runs
    calls = []
    monkeypatch.setattr(ss, "_run", lambda *a, **k: calls.append(a) or 0)

    # When  an undigested image ref is asked for
    try:
        ss.scan_image("ghcr.io/asimov-agent/llgenie/agent:latest", slug="agent")
    except SystemExit as exc:
        # Then  it is refused by name and no scanner ever ran
        assert "digest" in str(exc), str(exc)
        assert calls == []
    else:
        raise AssertionError("an undigested image target was accepted")


def test_an_image_scan_runs_the_three_stage_shape_against_the_digest(tmp_path, monkeypatch):
    """Trivy image + Syft SBOM + Grype-on-that-SBOM, all three addressed by digest, all writing
    into the reports dir mounted for the scan (issue #2706)."""

    # Given the docker stub answering the pinned scanner images, and a reports dir to mount
    log = _docker_stub(tmp_path, monkeypatch, pull_ok=True, inspect_ok=True)
    monkeypatch.setenv("DOCKER_STUB_RUN", "1")  # the `docker run` of each scanner exits 0
    reports = tmp_path / "reports"
    monkeypatch.setattr(ss, "REPORTS", reports)

    # When  the published image is scanned
    rc = ss.scan_image(IMAGE_REF, slug="agent")

    # Then  all three scanner runs ran, each carrying the exact digest-pinned target
    assert rc == 0
    runs = [json.loads(l) for l in log.read_text().splitlines() if json.loads(l)[0] == "run"]
    assert len(runs) == 3, runs
    for argv in runs:
        # the mount is the reports dir (writable), not the checkout: the target is a registry ref
        assert f"{reports.resolve()}:/reports:rw" in argv
        assert ":/work" not in " ".join(argv)
    # trivy and Syft carry the digest-pinned target itself; Grype reads the SBOM Syft wrote
    target_runs = [a for a in runs if IMAGE_REF in a]
    assert len(target_runs) == 2, runs
    kinds = {" ".join(a) for a in runs}
    assert any("image --severity" in k and " --scanners vuln " in f" {k} " for k in kinds), kinds
    assert any("cyclonedx-json=/reports/image-agent.cdx.json" in k for k in kinds), kinds
    assert any("sbom:/reports/image-agent.cdx.json" in k for k in kinds), kinds

    # And   the exact ref scanned is recorded so `findings()` can name the image
    meta = json.loads((reports / "image-agent.meta.json").read_text(encoding="utf-8"))
    assert meta["ref"] == IMAGE_REF


def test_scan_targets_are_pinned_to_the_digest_the_registry_serves(tmp_path, monkeypatch):
    """An engine entry resolves to its CURRENT pinned tag and every target gets the index digest
    the registry serves for it — the allow-list never carries a stale digest literal (issue #2706)."""

    # Given a manifest with one engine entry and one plain ref, and stubs for both resolution seams
    manifest = {"images": [
        {"name": "llama-cpp-cuda", "engine": "llama.cpp", "variant": "cuda"},
        {"name": "agent", "ref": "ghcr.io/asimov-agent/llgenie/agent:latest"},
    ]}
    monkeypatch.setattr(ss, "_resolve_engine_ref",
                        lambda engine, variant: f"ghcr.io/x/llama-cpp:hash1234-{variant}")
    monkeypatch.setattr(ss, "registry_manifest_digests",
                        lambda ref: {"index": "sha256:" + "cd" * 32})

    # When  the targets are resolved
    targets = ss.resolve_scan_targets(manifest)

    # Then  each slug maps to its ref@sha256:<64 hex> — no target leaves undigested
    assert [slug for slug, _ in targets] == ["llama-cpp-cuda", "agent"]
    for _, ref in targets:
        assert re.fullmatch(r".*@sha256:[0-9a-f]{64}", ref), ref


def test_an_unpublished_image_fails_the_lane_instead_of_being_skipped(tmp_path, monkeypatch):
    """An allow-list entry the registry has no digest for is a hard failure, never a silent skip
    (issue #2706): a scan lane that quietly skipped unpublished cells proves nothing."""

    # Given a manifest entry whose image the registry does not serve
    manifest = {"images": [{"name": "ghost", "ref": "ghcr.io/x/ghost:latest"}]}
    monkeypatch.setattr(ss, "registry_manifest_digests", lambda ref: {})

    # When  the lane resolves its targets
    try:
        ss.resolve_scan_targets(manifest)
    except SystemExit as exc:
        # Then  the lane says so, naming the ref
        assert "no index digest" in str(exc) and "ghost" in str(exc), str(exc)
    else:
        raise AssertionError("an unpublished image was skipped instead of failing the lane")


def test_image_reports_flow_through_findings_tagged_with_the_exact_image(tmp_path):
    """`image-*.trivy.json` / `image-*.grype.json` are read by the SAME normalisers and every
    finding names the `ref@digest` recorded in its meta file (issue #2706)."""

    # Given image reports and their meta companion, but no tree reports
    d = _reports(tmp_path, **{"image-agent.trivy": TRIVY_HIGH, "image-agent.grype": GRYPE_ONE})
    (d / "image-agent.meta.json").write_text(json.dumps({"ref": IMAGE_REF}), encoding="utf-8")

    # When  findings are normalized
    items = ss.findings(d)

    # Then  both sources flow through, each tagged with the exact image it was seen in
    assert len(items) == 2, items
    assert {i["source"] for i in items} == {"trivy", "grype"}
    for item in items:
        assert item.get("image") == IMAGE_REF, item


def test_an_image_finding_is_gated_by_the_same_policy(tmp_path):
    """A HIGH finding inside a published image gates a full-mode run and stays report-only for a
    PR event — the pipeline does not distinguish an image finding from a tree finding (issue #2706)."""

    # Given only an image report with a HIGH vulnerability that has a fix
    d = _reports(tmp_path, **{"image-agent.trivy": TRIVY_HIGH})
    (d / "image-agent.meta.json").write_text(json.dumps({"ref": IMAGE_REF}), encoding="utf-8")
    items = ss.findings(d)

    # When  the policy modes decide
    # Then  full mode gates on it, pr mode records it
    assert ss.blocking(items, POLICY, "full") != []
    assert ss.blocking(items, POLICY, "pr") == []


def test_check_refuses_an_empty_or_ill_formed_allow_list(tmp_path, monkeypatch):
    """The gate that prevents the silent skip (issue #2706): no manifest, an empty allow-list, an
    engine entry without a variant, or a missing fixture declaration all red `check`."""

    manifest = tmp_path / "scanned-images.json"
    monkeypatch.setattr(ss, "SCANNED_IMAGES", manifest)

    def write(payload: dict) -> int:
        manifest.write_text(json.dumps(payload), encoding="utf-8")
        return ss.check()

    # Given/Then each broken shape reds the gate on its own problem
    assert write({"images": [], "fixture": {"name": "fx", "ref": "r"}}) == 1          # empty list
    assert write({"images": [{"name": "e", "engine": "llama.cpp"}],
                  "fixture": {"name": "fx", "ref": "r"}}) == 1                        # no variant
    assert write({"images": [{"name": "e", "ref": "ghcr.io/x/y:tag"}]}) == 1          # no fixture
    assert write({"images": [{"name": "bad name", "ref": "ghcr.io/x/y:tag"}],
                  "fixture": {"name": "fx", "ref": "r"}}) == 1                        # bad slug


def test_the_committed_allow_list_and_both_lane_wirings_exist():
    """The real tree: the allow-list names at least one image and a fixture, BOTH lanes carry their
    scan step, and every engine entry resolves to a pinned GHCR ref (issue #2706)."""

    # Given the committed manifest and the two workflows
    manifest = json.loads((REPO / "containers" / "scanned-images.json").read_text(encoding="utf-8"))
    security_lane = (REPO / ".github" / "workflows" / "security-scan.yml").read_text(encoding="utf-8")
    engine_lane = (REPO / ".github" / "workflows" / "engine-build.yml").read_text(encoding="utf-8")

    # When  they are read for the lane's hard requirements
    # Then  the allow-list is non-empty, the fixture is declared, and each lane carries its step
    assert manifest.get("images"), manifest
    assert (manifest.get("fixture") or {}).get("ref"), manifest
    assert "make security-scan-images" in security_lane
    assert "make security-scan-fixture" in security_lane
    assert "make security-scan-published" in engine_lane

    # And   every engine entry resolves through the pinned params to a registry ref
    for entry in manifest["images"]:
        if entry.get("engine"):
            ref = ss._resolve_engine_ref(entry["engine"], entry["variant"])
            assert ref.startswith("ghcr.io/asimov-agent/llgenie/"), ref


def _fixture_manifest(tmp_path, monkeypatch) -> dict:
    """A manifest whose fixture slug/ref the fixture step will use, with the registry stubbed."""
    manifest = {"images": [{"name": "agent", "ref": "ghcr.io/x/agent:latest"}],
                "fixture": {"name": "fx", "ref": "docker.io/library/alpine:3.15.1"}}
    path = tmp_path / "scanned-images.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(ss, "SCANNED_IMAGES", path)
    monkeypatch.setattr(ss, "registry_manifest_digests",
                        lambda ref: {"index": "sha256:" + "ef" * 32})
    monkeypatch.setattr(ss, "REPORTS", tmp_path / "reports")
    return manifest


def test_the_fixture_fails_loudly_when_it_proves_nothing(tmp_path, monkeypatch):
    """A known-vulnerable image the scanners produce no report for is a BROKEN PROOF and exits
    non-zero — never a clean green (issue #2706)."""

    # Given the fixture manifest and a container run that writes no reports at all
    _fixture_manifest(tmp_path, monkeypatch)
    monkeypatch.setattr(ss, "_run", lambda *a, **k: 0)

    # When  the fixture step runs
    rc = ss.scan_image_fixture()

    # Then  the proof failing is the step failing
    assert rc == 1


def test_the_fixture_proves_the_image_scan_path_end_to_end(tmp_path, monkeypatch):
    """With the fixture's reports present (the shape the real scan writes), the step normalizes
    them through `findings()` and passes — the loud AC proof (issue #2706)."""

    # Given the fixture manifest, a stubbed run, and the reports a real run would have written
    _fixture_manifest(tmp_path, monkeypatch)
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "image-fx.trivy.json").write_text(json.dumps(TRIVY_HIGH), encoding="utf-8")
    (reports / "image-fx.meta.json").write_text(
        json.dumps({"ref": "docker.io/library/alpine:3.15.1@sha256:" + "ef" * 32}), encoding="utf-8")
    monkeypatch.setattr(ss, "_run", lambda *a, **k: 0)

    # When  the fixture step runs
    rc = ss.scan_image_fixture()

    # Then  the finding proves the path and the step passes
    assert rc == 0
