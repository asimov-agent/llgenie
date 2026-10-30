"""The architecture census gate refers to the TREE AT THE NAMED SHA, not HEAD (#1053).

Before #1053 `measure()` counted `git ls-tree … HEAD` and `check()` compared the pointer's tree count
against HEAD, so every PR that added a file had to rewrite the one shared `docs/ARCHITECTURE.md`
census block — and the pointer it was forced to write named the PR's own head, which the squash-merge
then orphaned (the #1048 → #1051 → #1052 red chain). The fix makes the referent the pointer's tree and
requires the pointer be an ancestor of HEAD.

Each test drives the REAL `check()` against a throwaway git repo, so the behaviour is asserted where it
can regress, not against a copy of the logic:

  * a branch that adds files but leaves the doc untouched passes (its doc names a main ancestor);
  * a doc whose count disagrees with the tree at the pointer's sha still reds (teeth kept);
  * a pointer that is a real commit but NOT an ancestor of HEAD reds, naming the sha;
  * a missing pointer reds, naming docs/ARCHITECTURE.md.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import check_architecture_census as cac  # noqa: E402


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                          check=True).stdout.strip()


def _commit(root: Path, msg: str) -> str:
    _git(root, "add", "-A")
    _git(root, "-c", "user.name=T", "-c", "user.email=t@e.x", "commit", "-q", "-m", msg)
    return _git(root, "rev-parse", "HEAD")


def _doc(root: Path, pointer: str, tracked: int = 3) -> None:
    """Write a minimal ARCHITECTURE.md whose census claims match a 3-dir/3-file base tree."""
    body = (
        f"The tree is {tracked} tracked files: `data/` 1, `skills/` 1, `containers/` 1, `tests/` 1, "
        f"`scripts/` 1, `openspec/` 1, `agent-wiki/` 0 and `docs/` 1 "
        f"(measured at `{pointer}`) and ({2} changes) and ({0} entries) and 1 `tests/test_*.py`.\n"
    )
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs" / "ARCHITECTURE.md").write_text(body)


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    """A throwaway repo with a small fixed tree; REPO_ROOT is redirected to it."""
    root = tmp_path / "r"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    for d in ("data", "skills", "containers", "tests", "scripts", "openspec", "docs"):
        (root / d).mkdir()
        (root / d / "f.txt").write_text("x")
    (root / "tests" / "test_one.py").write_text("# t\n")
    (root / "openspec" / "changes" / "a").mkdir(parents=True)
    (root / "openspec" / "changes" / "a" / "proposal.md").write_text("p\n")
    (root / "openspec" / "changes" / "b").mkdir(parents=True)
    (root / "openspec" / "changes" / "b" / "proposal.md").write_text("p\n")
    (root / "agent-wiki").mkdir()
    base = _commit(root, "base")
    # write the doc describing the base tree exactly, then commit it too (its own tracked count = 1 docs file)
    m = None
    monkeypatch.setattr(cac, "REPO_ROOT", root)
    m = cac.measure(base)
    (root / "docs" / "ARCHITECTURE.md").write_text(
        f"The tree is {m['tracked']} tracked files: `data/` {m['data']}, `skills/` {m['skills']}, "
        f"`containers/` {m['containers']}, `tests/` {m['tests']}, `scripts/` {m['scripts']}, "
        f"`openspec/` {m['openspec']}, `agent-wiki/` {m['agent-wiki']} and `docs/` {m['docs']} "
        f"(measured at `{base[:7]}`) and ({m['openspec-changes']} changes) and "
        f"({m['agent-wiki']} entries) and {m['test_py']} `tests/test_*.py`.\n"
    )
    doc_commit = _commit(root, "doc")
    return root, base, doc_commit


def test_a_branch_that_adds_files_but_leaves_the_doc_untouched_passes(repo, monkeypatch, capsys):
    """Acceptance #1: adding files must not force a census edit — the doc names a main ancestor (#1053)."""
    root, base, doc_commit = repo
    monkeypatch.setattr(cac, "REPO_ROOT", root)
    # a new branch off the doc commit that adds two files and does NOT touch the doc
    _git(root, "checkout", "-q", "-b", "feature", doc_commit)
    (root / "scripts" / "extra1.py").write_text("x")
    (root / "scripts" / "extra2.py").write_text("x")
    _commit(root, "add two files")
    assert cac.measure("HEAD")["tracked"] == cac.measure(doc_commit)["tracked"] + 2  # really added files
    # the doc still names doc_commit (an ancestor); its tree count matches the doc
    assert cac.check() == 0, capsys.readouterr().out


def test_a_doc_whose_count_disagrees_with_the_tree_at_the_pointer_still_reds(repo, monkeypatch, capsys):
    """Teeth kept: the numbers are checked against the pointer's tree, not HEAD."""
    root, base, doc_commit = repo
    monkeypatch.setattr(cac, "REPO_ROOT", root)
    doc = root / "docs" / "ARCHITECTURE.md"
    doc.write_text(doc.read_text().replace("The tree is", "The tree is 1", 1))  # wrong count
    assert cac.check() == 1
    assert "tracked" in capsys.readouterr().out


def test_a_real_but_non_ancestor_pointer_reds_naming_the_sha(repo, monkeypatch, capsys):
    """Acceptance #5b / #1043 reachability: a pointer to a branch head (not an ancestor) reds."""
    root, base, doc_commit = repo
    # a commit on a side branch that main will NOT contain
    _git(root, "checkout", "-q", "-b", "side", doc_commit)
    (root / "scripts" / "side.py").write_text("x")
    side = _commit(root, "side")
    _git(root, "checkout", "-q", "main")
    _git(root, "checkout", "-q", "-b", "elsewhere", doc_commit)
    (root / "scripts" / "elsewhere.txt").write_text("x")   # a real change so the branch diverges from `side`
    _commit(root, "elsewhere")  # HEAD diverges from `side`
    # point the doc at the non-ancestor `side` (rewrite whatever pointer is there)
    import re as _re
    docp = root / "docs" / "ARCHITECTURE.md"
    docp.write_text(_re.sub(r"measured at `[0-9a-f]+`", f"measured at `{side[:7]}`", docp.read_text()))
    monkeypatch.setattr(cac, "REPO_ROOT", root)
    assert cac.check() == 1
    out = capsys.readouterr().out
    assert side[:7] in out and "NOT an ancestor" in out


def test_a_missing_pointer_reds_naming_architecture_md(repo, monkeypatch, capsys):
    """Acceptance #4: no pointer reds, and the message names docs/ARCHITECTURE.md."""
    root, base, doc_commit = repo
    monkeypatch.setattr(cac, "REPO_ROOT", root)
    doc = root / "docs" / "ARCHITECTURE.md"
    import re
    doc.write_text(re.sub(r"\(measured at `[0-9a-f]+`\)", "", doc.read_text()))
    assert cac.check() == 1
    assert "docs/ARCHITECTURE.md" in capsys.readouterr().out
