"""The scan's own fix (issue #738): the floor a finding demands, compiled into the pins.

Every rule is exercised on a real artefact: a real trivy report on disk, a real `tools/security-floor
s.in`, real compiled `requirements*.txt`, and a real git checkout with a real bare `origin` for the
bump PR. Only GitHub is stood in for — by a `gh` executable that records its argv — and the
requirements GENERATOR is a recording seam (the real one needs docker, which the hermetic suite must
not). `make` is a real executable in the fixture root, so "gates red => no PR" is a decision the code
makes rather than a mocked return value.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import security_bumps as sbu  # noqa: E402

#: The exact shape of the findings that failed run 40525155122 (a push to main).
CERTIFI = {"VulnerabilityID": "GHSA-6q48-6c7w-9gw2", "PkgName": "certifi",
           "InstalledVersion": "2026.7.22", "FixedVersion": "2026.10.18", "Severity": "CRITICAL"}
FILELOCK = {"VulnerabilityID": "CVE-2026-112940", "PkgName": "filelock",
            "InstalledVersion": "3.32.5", "FixedVersion": "4.2.1", "Severity": "HIGH"}
URLLIB_A = {"VulnerabilityID": "CVE-2026-97687", "PkgName": "urllib3",
            "InstalledVersion": "2.7.0", "FixedVersion": "2.8.0", "Severity": "HIGH"}
URLLIB_B = {"VulnerabilityID": "CVE-2026-97689", "PkgName": "urllib3",
            "InstalledVersion": "2.7.0", "FixedVersion": "2.9.0", "Severity": "HIGH"}
NO_FIX = {"VulnerabilityID": "CVE-2026-1", "PkgName": "libfoo",
          "InstalledVersion": "1.0", "FixedVersion": "", "Severity": "CRITICAL"}
POLICY = {"fail_on": ["critical", "high"], "pr_fail_on": [], "require_fix": True,
          "issue_severities": ["critical", "high"],
          "enforce_events": ["schedule", "workflow_dispatch"]}


def _items(*vulns) -> list[dict]:
    return [{"id": v["VulnerabilityID"], "package": v["PkgName"], "current": v["InstalledVersion"],
             "fixed": v["FixedVersion"], "severity": v["Severity"].lower(), "source": "trivy"}
            for v in vulns]


def _reports(tmp_path: Path, *vulns) -> Path:
    d = tmp_path / "reports"
    d.mkdir(parents=True, exist_ok=True)
    (d / "trivy.json").write_text(json.dumps({"Results": [{"Vulnerabilities": list(vulns)}]}),
                                  encoding="utf-8")
    return d


def _gh_stub(tmp_path: Path, monkeypatch, issues: list[dict] | None = None) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    log = tmp_path / "gh-calls.log"
    stub = tmp_path / "gh"
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "open(os.environ['GH_STUB_LOG'], 'a').write(' '.join(sys.argv[1:]) + '\\n')\n"
        "if sys.argv[1:3] == ['issue', 'list']:\n"
        "    print(os.environ.get('GH_STUB_ISSUES', '[]'))\n"
        "elif sys.argv[1:3] == ['pr', 'list']:\n"
        "    print(os.environ.get('GH_STUB_PRS', '[]'))\n"
        "elif sys.argv[1:2] == ['pr']:\n"
        "    print('https://github.com/o/r/pull/9')\n"
        "else:\n"
        "    print('ok')\n",
        encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")
    monkeypatch.setenv("GH_STUB_LOG", str(log))
    monkeypatch.setenv("GH_STUB_ISSUES", json.dumps(issues or []))
    monkeypatch.setenv("GH_STUB_PRS", "[]")
    return log


def _root(tmp_path: Path, compiled: dict[str, str] | None = None, gate_exit: int = 0) -> Path:
    """A real checkout: both `.in` files, both compiled files, a bare `origin`, a real `make`."""
    root = tmp_path / "work"
    (root / "tools").mkdir(parents=True)
    compiled = compiled if compiled is not None else {"certifi": "2026.7.22", "filelock": "3.32.5",
                                                      "urllib3": "2.7.0"}
    (root / "tools" / "requirements.in").write_text(
        "numpy\ngguf==0.19.1\n-c security-floors.in\n", encoding="utf-8")
    (root / "tools" / "requirements-dev.in").write_text(
        "pytest==8.3.5\n-c security-floors.in\n", encoding="utf-8")
    (root / "tools" / "requirements.txt").write_text(
        "".join(f"{pkg}=={ver}\n" for pkg, ver in compiled.items()), encoding="utf-8")
    (root / "tools" / "requirements-dev.txt").write_text("pytest==8.3.5\n", encoding="utf-8")
    (root / "tools" / "security-floors.in").write_text(sbu.HEADER, encoding="utf-8")
    targets = list(sbu.GATES) + list(sbu.GENERATORS)
    (root / "Makefile").write_text(
        "".join(f"{t}:\n\t@true\n" if gate_exit == 0 else f"{t}:\n\t@false\n" for t in targets),
        encoding="utf-8")
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", str(bare)], check=True)
    # A real checkout stands on `main` and has `origin/main`: the bot measures the `AGENTS:`/`BASE:`
    # stamp's rulebook there before it opens the PR (issue #2050), so the fixture must offer it.
    (root / "AGENTS.md").write_text("# Rules\n\n## Problem\n", encoding="utf-8")
    for argv in (["git", "init", "-q", "-b", "main"], ["git", "add", "-A"],
                 ["git", "-c", "user.name=t", "-c", "user.email=t@example.com",
                  "commit", "-qm", "init"], ["git", "remote", "add", "origin", str(bare)],
                 ["git", "push", "-q", "-u", "origin", "main"]):
        subprocess.run(argv, cwd=root, check=True, capture_output=True)
    return root


def _generator(monkeypatch, fl_versions: dict[str, str] | None = None) -> list[list[str]]:
    """Stand in for the ONE generator: record the call, write what pip-compile would have written."""
    calls: list[list[str]] = []

    def fake(root: Path = REPO) -> int:
        calls.append(["regenerate", str(root)])
        text = (root / sbu.FLOORS).read_text(encoding="utf-8") if (root / sbu.FLOORS).is_file() else ""
        floors, _ = sbu.parse_floor_text(text)
        body = "".join(f"{pkg}=={fl_versions.get(pkg, ver) if fl_versions else ver}\n"
                       for pkg, ver in floors.items())
        (root / "tools" / "requirements.txt").write_text(body, encoding="utf-8")
        return 0

    monkeypatch.setattr(sbu, "regenerate", fake)
    return calls


def test_the_floor_is_the_maximum_of_the_minimums():
    """Two advisories on one package: one line, the higher of the two required minimums."""

    # Given urllib3 at 2.7.0 with fixes 2.8.0 and 2.9.0
    items = _items(URLLIB_A, URLLIB_B)

    # When  the floors are derived
    fl = sbu.floors(items, POLICY)

    # Then  the floor is the one version that clears both, and both advisories are named
    assert fl["urllib3"].version == "2.9.0"
    assert [a for _, a in fl["urllib3"].advisories] == ["CVE-2026-97687", "CVE-2026-97689"]


def test_a_finding_without_a_fix_is_not_a_floor():
    """`require_fix` is why an unfixable advisory can never become a pin nobody can reach."""

    # Given a critical with no fixed version
    items = _items(NO_FIX)

    # When  the floors are derived
    fl = sbu.floors(items, POLICY)

    # Then  it is not a floor at all
    assert fl == {}


def test_the_floor_ignores_a_fix_at_or_below_the_installed_version():
    """A stale report that names the installed version as "fixed" must not invent a downgrade."""

    # Given a fix equal to the installed version
    stale = dict(CERTIFI, FixedVersion="2026.7.22")

    # When  the floors are derived
    fl = sbu.floors(_items(stale), POLICY)

    # Then  nothing is floored
    assert fl == {}


def test_version_key_orders_the_scanner_versions():
    """Versions are compared numerically per component, not as strings."""

    # Given versions the scanners write
    # Then  the ordering is numeric per component, and a calver string sorts after its predecessor
    assert sbu.version_key("2.10.0") > sbu.version_key("2.9.0")
    assert sbu.version_key("2026.10.18") > sbu.version_key("2026.7.22")
    assert sbu.version_key("4.2.1") > sbu.version_key("3.32.5")


def test_a_dry_run_writes_nothing(tmp_path, monkeypatch):
    """`make security-bumps-plan` prints the floor and mutates nothing."""

    # Given a checkout whose compiled pins are below the reported fixes
    root = _root(tmp_path)
    reports = _reports(tmp_path, CERTIFI, FILELOCK, URLLIB_A, URLLIB_B)
    before = (root / "tools" / "requirements.txt").read_text(encoding="utf-8")

    # When  the plan runs
    rc = sbu.apply("o/r", root, dry=True, reports=reports)

    # Then  it exits 0, wrote no floor and touched no compiled pin
    assert rc == 0
    assert (root / "tools" / "security-floors.in").read_text(encoding="utf-8") == sbu.HEADER
    assert (root / "tools" / "requirements.txt").read_text(encoding="utf-8") == before


def test_apply_regenerates_the_compiled_pins(tmp_path, monkeypatch):
    """The floor is written, then BOTH compiled files are regenerated by the one generator."""

    # Given a checkout with stale transitive pins and the reports that failed run 40525155122
    root = _root(tmp_path)
    reports = _reports(tmp_path, CERTIFI, FILELOCK, URLLIB_A, URLLIB_B)
    _gh_stub(tmp_path / "bin", monkeypatch)
    calls = _generator(monkeypatch)

    # When  the bump applies
    rc = sbu.apply("o/r", root, dry=False, reports=reports)

    # Then  the floors file carries the scanner's own versions and the generator ran once
    assert rc == 0
    floors, problems = sbu.parse_floor_text((root / "tools" / "security-floors.in").read_text())
    assert problems == []
    assert floors == {"certifi": "2026.10.18", "filelock": "4.2.1", "urllib3": "2.9.0"}
    assert len(calls) == 1

    # And   the compiled pin moved to the generator's output, never by a hand edit in this module
    assert "urllib3==2.9.0" in (root / "tools" / "requirements.txt").read_text()


def test_an_unsatisfied_floor_after_regeneration_opens_no_pr(tmp_path, monkeypatch):
    """Green or nothing: pip-compile could not reach the floor, so no branch and no PR appear."""

    # Given a generator that cannot reach urllib3's floor
    root = _root(tmp_path)
    reports = _reports(tmp_path, URLLIB_A)
    log = _gh_stub(tmp_path / "bin", monkeypatch)
    _generator(monkeypatch, fl_versions={"urllib3": "2.7.9"})

    # When  the bump applies
    rc = sbu.apply("o/r", root, dry=False, reports=reports)

    # Then  it fails, the floor is reverted, and no PR was opened
    assert rc == 1
    assert (root / "tools" / "security-floors.in").read_text() == sbu.HEADER
    assert not log.is_file() or "pr create" not in log.read_text()


def test_a_red_gate_after_the_bump_opens_no_pr(tmp_path, monkeypatch):
    """A gate that fails after the regeneration reverts and pushes nothing."""

    # Given a checkout whose gates fail
    root = _root(tmp_path, gate_exit=1)
    reports = _reports(tmp_path, CERTIFI)
    log = _gh_stub(tmp_path / "bin", monkeypatch)
    _generator(monkeypatch)

    # When  the bump applies
    rc = sbu.apply("o/r", root, dry=False, reports=reports)

    # Then  it fails and no PR is opened
    assert rc == 1
    assert not log.is_file() or "pr create" not in log.read_text()


def test_the_pr_body_closes_the_matched_issues(tmp_path, monkeypatch):
    """One bump PR, closing every tagged issue it fixes, with the four required parts."""

    # Given two open tagged issues whose markers match the findings
    issues = [
        {"number": 41, "body": "<!-- security-finding: trivy:GHSA-6q48-6c7w-9gw2:certifi -->",
         "labels": [], "title": "security(critical): certifi"},
        {"number": 42, "body": "<!-- security-finding: trivy:CVE-2026-97687:urllib3 -->",
         "labels": [], "title": "security(high): urllib3"},
    ]
    root = _root(tmp_path)
    reports = _reports(tmp_path, CERTIFI, URLLIB_A)
    log = _gh_stub(tmp_path / "bin", monkeypatch, issues=issues)
    _generator(monkeypatch)

    # When  the bump applies
    rc = sbu.apply("o/r", root, dry=False, reports=reports)

    # Then  the PR body closes both issues and carries Issue/Fix/Benefit/Technical
    assert rc == 0
    calls = log.read_text()
    assert "pr create" in calls
    body = (root / ".git" / "security-bumps-pr-body.md").read_text()
    for part in ("Issue:", "Fix:", "Benefit:", "Technical:"):
        assert part in body
    assert "closes #41" in body and "closes #42" in body
    assert sbu.FLOORS.as_posix() in body


def test_a_pin_below_its_floor_fails_the_gate(tmp_path):
    """The committed floor is checked against the committed pins."""

    # Given a floor the compiled pin does not reach
    root = _root(tmp_path, compiled={"urllib3": "2.7.0"})
    (root / "tools" / "security-floors.in").write_text(
        sbu.HEADER + "urllib3>=2.8.0    # trivy CVE-1: 2.7.0 -> 2.8.0\n", encoding="utf-8")

    # When  the gate runs
    rc = sbu.check(root)

    # Then  it fails, naming the package and both versions
    assert rc == 1


def test_check_fails_without_the_include(tmp_path):
    """Without `-c security-floors.in` the floor would be a file nothing compiles."""

    # Given a checkout whose `.in` files lost the include
    root = _root(tmp_path)
    (root / "tools" / "requirements.in").write_text("numpy\n", encoding="utf-8")

    # When  the gate runs
    rc = sbu.check(root)

    # Then  it fails
    assert rc == 1


def test_a_floor_without_an_advisory_reason_fails_the_gate(tmp_path):
    """A floor a reviewer cannot trace to an advisory is not reviewable."""

    # Given a bare floor line
    root = _root(tmp_path)
    (root / "tools" / "security-floors.in").write_text(sbu.HEADER + "urllib3>=2.8.0\n",
                                                      encoding="utf-8")

    # When  the gate runs
    rc = sbu.check(root)

    # Then  it fails
    assert rc == 1


def test_the_committed_tree_satisfies_its_own_gate():
    """This repository's committed floor is well-formed, included and satisfied."""

    # Given this repository
    # When  the gate runs against it
    rc = sbu.check(REPO)

    # Then  it passes
    assert rc == 0
