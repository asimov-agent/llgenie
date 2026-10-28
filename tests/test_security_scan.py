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
import stat
import sys
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
GRYPE_ONE = {"matches": [{
    "vulnerability": {"id": "GHSA-1", "severity": "Critical"},
    "artifact": {"name": "openssl", "version": "3.0"},
    "fix": {"versions": ["3.1"]},
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


def _docker_stub(tmp_path: Path, monkeypatch, *, pull_ok: bool, build_ok: bool = True,
                 inspect_ok: bool = False) -> Path:
    """A real executable standing in for `docker`, so which branch the code takes is observable."""
    log = tmp_path / "docker.log"
    stub = tmp_path / "docker"
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "open(os.environ['DOCKER_STUB_LOG'], 'a').write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "which = sys.argv[1]\n"
        "ok = os.environ.get('DOCKER_STUB_' + which.upper(), '0') == '1'\n"
        "sys.exit(0 if ok else 1)\n",
        encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("DOCKER_STUB_LOG", str(log))
    monkeypatch.setenv("DOCKER_STUB_INSPECT", "1" if inspect_ok else "0")
    monkeypatch.setenv("DOCKER_STUB_PULL", "1" if pull_ok else "0")
    monkeypatch.setenv("DOCKER_STUB_BUILD", "1" if build_ok else "0")
    monkeypatch.setattr(ss, "RUNTIME", str(stub))
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


def test_an_unpublished_image_is_built_from_the_same_dockerfile(tmp_path, monkeypatch):
    """Before the first publish (and on a fork run) the SAME Dockerfile is built, never skipped."""

    # Given a docker whose pull fails but whose build succeeds
    log = _docker_stub(tmp_path, monkeypatch, pull_ok=False, build_ok=True)

    # When  the image is resolved
    ref = ss.ensure_image("trivy")

    # Then  it was built from containers/scanners/trivy and tagged with the requested ref
    builds = [json.loads(l) for l in log.read_text().splitlines() if '"build"' in l]
    assert len(builds) == 1
    assert builds[0][-1].endswith("containers/scanners/trivy")
    assert ref in builds[0]
    assert ref == ss.image_ref("trivy")


def test_a_failed_build_is_loud(tmp_path, monkeypatch):
    """A scanner that cannot be obtained at all fails the run; it is never a silent skip."""

    # Given a docker whose pull AND build fail
    _docker_stub(tmp_path, monkeypatch, pull_ok=False, build_ok=False)

    # When  the image is resolved
    try:
        ss.ensure_image("trivy")
    except SystemExit as exc:
        # Then  the run refuses, naming the scanner
        assert "cannot build trivy" in str(exc)
    else:
        raise AssertionError("a scanner that could not be obtained was accepted")


def test_semgrep_uses_an_explicit_pack_not_auto(tmp_path, monkeypatch):
    """`--config auto` is refused by Semgrep when metrics are off, so an explicit pack is pinned."""

    # Given a docker stub that records the argv
    log = _docker_stub(tmp_path, monkeypatch, pull_ok=True, inspect_ok=True)

    # When  a semgrep scan is launched
    ss.scan("semgrep")

    # Then  the argv names an explicit pack and keeps metrics off
    runs = [json.loads(l) for l in log.read_text().splitlines() if json.loads(l)[0] == "run"]
    argv = runs[-1]
    assert "--config=p/default" in argv
    assert "auto" not in argv
    assert "--metrics" in argv and "off" in argv


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
