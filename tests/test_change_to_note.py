"""The change->note direction of the change-record rule (issue #1123).

`check-docs` enforced note -> fragment but never change -> note, so a behavioural change with no
`agent-wiki/` note merged green. These tests exercise BOTH evidence lines: a behavioural change
with no note must produce a problem, and a change the rule exempts (test-only / record-only) must
produce none. They assert behaviour, not an exact file list.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check_docs  # noqa: E402


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "README.md").write_text("base\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "base")
    return tmp_path


def _commit(repo: Path, path: str, text: str = "x\n") -> None:
    p = repo / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", f"touch {path}")


# --- owes_note: the classification, asserted on behaviour not an exact list ---------------

@pytest.mark.parametrize("path", [
    "scripts/anything.py", "agents/llgenie-x/SOUL.md", "agents/llgenie-x/skills/s/SKILL.md",
    "agents/manifest.json", "docs/BOTS.md", ".github/workflows/ci.yml", "Makefile",
    "data/models.json", "containers/ci/Dockerfile", "openspec/changes/x/tasks.md",
])
def test_a_behavioural_surface_owes_a_note(path: str) -> None:
    assert check_docs.owes_note([path]) is True


@pytest.mark.parametrize("path", [
    "tests/test_x.py", "tests/fixtures/y.json", "agent-wiki/n.md",
    "docs/changes.d/n.md", "CHANGES.md", "README.md", ".gitignore",
])
def test_a_test_or_record_path_owes_no_note(path: str) -> None:
    assert check_docs.owes_note([path]) is False


# --- change_note_problems: both evidence lines end to end over a real git range -----------

def test_a_behavioural_change_with_no_note_fails(repo: Path) -> None:
    _commit(repo, "scripts/thing.py")
    problems = check_docs.change_note_problems(repo, "HEAD~1")
    assert problems, "a scripts/ change with no agent-wiki note must be a problem"
    assert "scripts/thing.py" in problems[0]
    assert "agent-wiki/" in problems[0]


def test_a_behavioural_change_with_a_note_passes(repo: Path) -> None:
    _commit(repo, "scripts/thing.py")
    _commit(repo, "agent-wiki/2026-01-01-thing.md", "# thing\n\nIssue: #1\n")
    assert check_docs.change_note_problems(repo, "HEAD~2") == []


def test_a_test_only_change_passes(repo: Path) -> None:
    _commit(repo, "tests/test_thing.py")
    assert check_docs.change_note_problems(repo, "HEAD~1") == []


def test_an_empty_range_passes(repo: Path) -> None:
    assert check_docs.change_note_problems(repo, "HEAD") == []
