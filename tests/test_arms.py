from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import check_arms as am


def _run(args: list[str], monkeypatch) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(REPO / "scripts" / "check_arms.py"), *args],
                          capture_output=True, text=True, cwd=REPO)


def _fake_gh(tmp_path: Path, prs: list[dict]) -> Path:
    bindir = tmp_path / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    gh = bindir / "gh"
    gh.write_text(f'''#!{sys.executable}
import json, sys
if sys.argv[1:3] == ["pr", "list"]:
    print({json.dumps(prs)!r})
    sys.exit(0)
print(json.dumps(sys.argv[1:]), file=sys.stderr); sys.exit(1)
''')
    gh.chmod(0o755)
    return bindir


def _pr(number, *, base="main", draft=False, mergeable="MERGEABLE", auto=None):
    return {"number": number, "title": f"PR {number}", "isDraft": draft,
            "baseRefName": base, "mergeable": mergeable, "autoMergeRequest": auto}


def test_a_finished_mergeable_main_pr_that_is_unarmed_is_a_finding(tmp_path, monkeypatch):
    """Prevents (rule 16): a finished PR left on the board is invisible to every sweep."""
    bindir = _fake_gh(tmp_path, [_pr(1, auto=None), _pr(2, auto={"mergeMethod": "SQUASH"})])
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    out = _run(["check"], monkeypatch)
    assert out.returncode == 1, out.stdout + out.stderr
    assert "1/2 armed" in out.stdout, out.stdout


def test_a_draft_or_stacked_base_owes_no_arm(tmp_path, monkeypatch):
    """A draft (not finished) and a stacked base (cannot be armed, #964) must not be flagged."""
    bindir = _fake_gh(tmp_path, [_pr(1, base="feat/x", auto=None), _pr(2, draft=True, auto=None)])
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    out = _run(["check"], monkeypatch)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "0/2 armed" in out.stdout, out.stdout


def test_a_conflicted_pr_is_not_finished_and_is_skipped(tmp_path, monkeypatch):
    """An unmergeable PR has nothing to arm into yet."""
    bindir = _fake_gh(tmp_path, [_pr(1, mergeable="DIRTY", auto=None)])
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    out = _run(["check"], monkeypatch)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "not mergeable: DIRTY" in out.stdout, out.stdout


def test_finished_unarmed_decision_branches_on_the_right_fields():
    assert am.finished_unarmed(_pr(1, auto=None)) is True
    assert am.finished_unarmed(_pr(1, auto={"mergeMethod": "SQUASH"})) is False
    assert am.finished_unarmed(_pr(1, draft=True, auto=None)) is False
    assert am.finished_unarmed(_pr(1, base="feat/x", auto=None)) is False
    assert am.finished_unarmed(_pr(1, mergeable="DIRTY", auto=None)) is False
