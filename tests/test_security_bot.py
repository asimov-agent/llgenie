"""The remediation bot (issue #717): one auto-fixable issue -> one green PR, or nothing.

The bot's business logic is exercised for real: the issue body is parsed from text the issuer
(#716) writes, the pin is edited in a real file, and the git side runs against a real repository
with a real bare `origin`. Only GitHub is stood in for, by a `gh` executable that records its argv —
and `make` is a real executable in the fixture root, so "gates red => no PR" is a real decision the
code makes, not a mocked return value.

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
from scripts import security_bot as sb

BODY_OK = """<!-- security-finding: trivy:CVE-2024-1:numpy -->

**Advisory:** `CVE-2024-1` — scanner: `trivy`
**Affected package:** `numpy`
**Current → fixed:** `1.26.0` → `1.26.4`
**Severity:** `critical`
**Scan run:** https://github.com/o/r/actions/runs/1

### Suggested action

Bump `numpy` from `1.26.0` to `1.26.4`.

### Not covered

- nothing
"""

ISSUES = [{
    "number": 42, "title": "security(critical): CVE-2024-1 in numpy (trivy)", "body": BODY_OK,
    "createdAt": "2026-10-27T05:00:00Z",
    "labels": [{"name": "security"}, {"name": "vulnerability"}, {"name": "auto-fixable"}],
}]


def _gh_stub(tmp_path: Path, monkeypatch, issues: str = "[]") -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    log = tmp_path / "gh-calls.log"
    stub = tmp_path / "gh"
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "open(os.environ['GH_STUB_LOG'], 'a').write(' '.join(sys.argv[1:]) + '\\n')\n"
        "if sys.argv[1:2] == ['issue'] and 'list' in sys.argv:\n"
        "    print(os.environ.get('GH_STUB_LIST', '[]'))\n"
        "elif sys.argv[1:2] == ['pr']:\n"
        "    print('https://github.com/o/r/pull/7')\n"
        "else:\n"
        "    print('ok')\n",
        encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")
    monkeypatch.setenv("GH_STUB_LOG", str(log))
    monkeypatch.setenv("GH_STUB_LIST", issues)
    return log


def _root(tmp_path: Path, gate_exit: int = 0) -> Path:
    """A real checkout: a `.in` pin, a bare `origin`, and a `make` whose gates exit as asked."""
    root = tmp_path / "work"
    (root / "tools").mkdir(parents=True)
    (root / "tools" / "requirements.in").write_text("numpy==1.26.0\ngguf==0.19.0\n", encoding="utf-8")
    (root / "Makefile").write_text(
        "".join(f"{t}:\n\t@true\n" for t in sb.GATES) if gate_exit == 0 else
        "".join(f"{t}:\n\t@false\n" for t in sb.GATES), encoding="utf-8")
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", str(bare)], check=True)
    for argv in (["git", "init", "-q"], ["git", "add", "-A"],
                 ["git", "-c", "user.name=t", "-c", "user.email=t@example.com",
                  "commit", "-qm", "init"], ["git", "remote", "add", "origin", str(bare)]):
        subprocess.run(argv, cwd=root, check=True, capture_output=True)
    return root


def test_select_takes_the_oldest_auto_fixable_issue(tmp_path, monkeypatch):
    """Selection needs all three labels, and the oldest wins — never a random pick."""

    # Given two eligible issues, the second older, plus one missing a label
    issues = [
        {"number": 3, "body": "", "createdAt": "2026-10-27T06:00:00Z",
         "labels": [{"name": "security"}, {"name": "vulnerability"}, {"name": "auto-fixable"}]},
        {"number": 2, "body": "", "createdAt": "2026-10-26T06:00:00Z",
         "labels": [{"name": "security"}, {"name": "vulnerability"}, {"name": "auto-fixable"}]},
        {"number": 1, "body": "", "createdAt": "2026-10-25T06:00:00Z",
         "labels": [{"name": "security"}]},
    ]
    _gh_stub(tmp_path, monkeypatch, json.dumps(issues))

    # When  the bot selects
    issue = sb.select("o/r")

    # Then  it is the oldest issue that carries every select label
    assert issue["number"] == 2


def test_select_returns_none_when_nothing_is_eligible(tmp_path, monkeypatch):
    """No eligible issue is a quiet no-op, not an error."""

    # Given no open issue
    _gh_stub(tmp_path, monkeypatch, "[]")

    # When  the bot selects
    # Then  it reports nothing to do
    assert sb.select("o/r") is None


def test_parse_reads_package_and_versions_from_the_issuer_body():
    """The bot parses exactly the body #716 writes — that format is the contract."""

    # Given an issue body from the issuer
    # When  it is parsed
    target = sb.parse(ISSUES[0])

    # Then  package, current, fixed and the marker come out
    assert (target.package, target.current, target.fixed) == ("numpy", "1.26.0", "1.26.4")
    assert target.marker == "<!-- security-finding: trivy:CVE-2024-1:numpy -->"
    assert target.component == "python"


def test_parse_refuses_a_body_without_the_lines():
    """A body that does not carry the package/version lines is refused, never guessed."""

    # Given an issue with no package line
    issue = {"number": 5, "body": "just a thought"}

    # When  it is parsed
    try:
        sb.parse(issue)
    except SystemExit as exc:
        # Then  the refusal names the format contract
        assert "refusing to guess" in str(exc)
    else:
        raise AssertionError("a body without the issuer's lines was accepted")


def test_apply_plan_finds_the_pin_and_leaves_compiled_files_alone(tmp_path):
    """Only the `.in` owns a pin; a compiled `.txt` is never an edit target."""

    # Given a checkout with the pin in requirements.in
    root = _root(tmp_path)
    target = sb.parse(ISSUES[0])

    # When  the plan is computed
    plan = sb.apply_plan(target, root)

    # Then  it names the .in line and the new pin
    path, before, after = plan
    assert path == root / "tools" / "requirements.in"
    assert (before, after) == ("numpy==1.26.0", "numpy==1.26.4")


def test_a_container_finding_is_refused_not_guessed(tmp_path):
    """A base-image advisory has no per-package pin: the bot comments and opens no PR."""

    # Given a container finding
    target = sb.Target(number=9, package="openssl", current="3.0", fixed="3.1",
                       component="container", marker="")

    # When  the plan is computed
    plan = sb.apply_plan(target, _root(tmp_path))

    # Then  there is no edit to make
    assert plan is None


def test_a_package_pinned_nowhere_is_refused(tmp_path):
    """An unknown package must not produce a hopeful edit."""

    # Given a finding for a package the .in does not pin
    target = sb.Target(number=10, package="requests", current="2.0", fixed="2.1",
                       component="python", marker="")

    # Then  there is no edit to make
    assert sb.apply_plan(target, _root(tmp_path)) is None


def test_red_gates_revert_the_edit_and_open_no_pr(tmp_path, monkeypatch):
    """Green or nothing: a red gate leaves the file untouched and opens NO PR."""

    # Given a checkout whose gates fail
    root = _root(tmp_path, gate_exit=1)
    log = _gh_stub(tmp_path / "stub", monkeypatch, json.dumps(ISSUES))
    before = (root / "tools" / "requirements.in").read_text(encoding="utf-8")

    # When  the bot applies
    rc = sb.apply("o/r", root)

    # Then  it fails, the pin is unchanged, and no PR was created
    assert rc == 1
    assert (root / "tools" / "requirements.in").read_text(encoding="utf-8") == before
    calls = log.read_text() if log.exists() else ""
    assert "pr create" not in calls
    assert "issue comment" in calls  # the reason was recorded on the issue instead


def test_green_gates_edit_push_and_open_the_pr(tmp_path, monkeypatch):
    """The happy path: one pin moves, one commit is pushed, the PR body carries the four parts."""

    # Given a clean checkout and an eligible issue
    root = _root(tmp_path)
    log = _gh_stub(tmp_path / "stub", monkeypatch, json.dumps(ISSUES))

    # When  the bot applies
    rc = sb.apply("o/r", root)

    # Then  the pin moved, a branch was pushed, and the PR body has Issue/Fix/Benefit/Technical
    assert rc == 0
    assert "numpy==1.26.4" in (root / "tools" / "requirements.in").read_text(encoding="utf-8")
    branches = subprocess.run(["git", "branch", "--list"], cwd=root, capture_output=True, text=True).stdout
    assert "fix/security-cve-2024-1-numpy" in branches
    pushed = subprocess.run(["git", "branch", "--list", "--remotes"], cwd=root,
                            capture_output=True, text=True).stdout
    assert "origin/fix/security-cve-2024-1-numpy" in pushed
    body = (root / ".git" / "security-bot-pr-body.md").read_text(encoding="utf-8")
    for part in ("Issue:", "Fix:", "Benefit:", "Technical:", "closes #42"):
        assert part in body, part
    assert "pr create" in log.read_text()


def test_dry_run_writes_nothing(tmp_path, monkeypatch):
    """`DRY=1` prints the plan and touches neither the file nor GitHub."""

    # Given a clean checkout
    root = _root(tmp_path)
    log = _gh_stub(tmp_path / "stub", monkeypatch, json.dumps(ISSUES))
    before = (root / "tools" / "requirements.in").read_text(encoding="utf-8")

    # When  the bot plans
    rc = sb.apply("o/r", root, dry=True)

    # Then  nothing changed and nothing was pushed
    assert rc == 0
    assert (root / "tools" / "requirements.in").read_text(encoding="utf-8") == before
    assert not log.exists() or "pr create" not in log.read_text()


def test_the_real_contract_is_sane():
    """The bot's labels exist in the issuer's roster and its pin sources are the `.in` files."""

    # Given this repository
    # When  the gate runs
    # Then  it passes
    assert sb.check(REPO) == 0
