"""The report-hygiene guard (issue #1292): a reporting leg names its evidence or stays silent.

A finding in this fleet is measured at a sha; who changed a file has no author-of-record in the commit
graph, so a blame sentence that says *whose* work did an adverse thing is a guess unless a sha is named.
This guard scans the reporting legs (emitted strings in `scripts/*.py` and workflow `name:`/`run:` lines)
and fails on any ownership-guess blame sentence that carries no evidence anchor.

The tests pin the contract from both sides:
- a stubbed blame sentence *without* a sha must red, and the same sentence *with* a `@<sha>` must pass
  (the acceptance criterion), in both active ("another lane advanced it") and passive ("the file was
  moved by another lane") voice;
- a negative control: a fixture reporting leg that emits "another lane advanced it" reds the check;
- the tree's own corrected prose passes: `scripts/agent_profile_sync.py`'s message names the mtime fact,
  never an owner, and the guard over the WHOLE repository stays green.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

from pathlib import Path

from scripts import check_report_hygiene as rh

REPO = Path(__file__).resolve().parent.parent


def _tree(tmp_path: Path, scripts: dict[str, str] = None, workflow: str = "") -> Path:
    """A fixture repository with the requested reporting legs."""
    root = tmp_path / "repo"
    (root / rh.SCRIPTS).mkdir(parents=True)
    (root / rh.WORKFLOWS).mkdir(parents=True)
    for name, body in (scripts or {}).items():
        (root / rh.SCRIPTS / name).write_text(body)
    if workflow:
        (root / rh.WORKFLOWS / "a.yml").write_text(workflow)
    return root


def test_active_blame_without_sha_is_a_violation(tmp_path: Path):
    """A reporting leg that blames 'another lane' with no sha is a guess, and the guard reds it."""

    # Given a reporting leg that emits an ownership-guess blame sentence with no sha
    root = _tree(tmp_path, scripts={"a.py": 'print("another lane advanced it")\n'})

    # When  the guard reads it
    items = rh.findings(root)

    # Then  the unanchored blame is a violation
    keys = [f["key"] for f in items]
    assert any("ownership-guess" in k for k in keys)


def test_active_blame_with_sha_passes(tmp_path: Path):
    """The same blame sentence anchored to a `@<sha>` is evidence, not a guess, and passes."""

    # Given the blame names the guilty sha
    root = _tree(tmp_path, scripts={"a.py": 'print("another lane advanced it at @a1b2c3d4e5f6789")\n'})

    # When  the guard reads it
    items = rh.findings(root)

    # Then  the sha gives it evidence and no violation is raised
    assert items == []


def test_passive_blame_without_sha_is_a_violation(tmp_path: Path):
    """Passive voice blames too: 'moved by another lane' with no sha is still a guess."""

    # Given a passive attribution with no evidence
    root = _tree(tmp_path, scripts={"a.py": 'print("the file was moved by another lane")\n'})

    # When / Then  it is a violation
    assert rh.findings(root)


def test_this_lane_own_advance_without_sha_is_a_violation(tmp_path: Path):
    """The issue names 'this lane' explicitly: a self-referential advance with no sha still reds."""

    # Given a leg that blames 'this lane' for advancing the head, no sha
    root = _tree(tmp_path, scripts={"a.py": 'print("this lane advanced the head without evidence")\n'})

    # When / Then  it is a violation
    assert rh.findings(root)


def test_workflow_run_blame_reds(tmp_path: Path):
    """The negative control reaches workflow legs too — a run: line that blames a lane reds."""

    # Given a workflow run: step that emits an ownership-guess blame sentence
    root = _tree(tmp_path, workflow='jobs:\n  j:\n    runs-on: ubuntu\n    steps:\n      - run: "another lane advanced it"\n')

    # When / Then  the check reds on the workflow leg
    assert rh.findings(root)


def test_agent_profile_sync_message_passes(tmp_path: Path):
    """The tree's own corrected message names the mtime fact, never an owner, and must never red.

    This is the acceptance criterion: the corrected `agent_profile_sync.py` message passes unchanged.
    """

    # Given the actual corrected message emitted by agent_profile_sync.py (mtime fact, no owner)
    body = (
        'print("REFUSED agents/a/SKILL.md: the live file was edited AFTER the tree copy was committed — "\n'
        '      "live 2026-11-01T10:00:00Z, source commit 2026-11-01T09:00:00Z — so a sync would overwrite "\n'
        '      "2,048 b with 1,024 b. Read the live file and merge deliberately, or pass --force.")\n'
    )
    root = _tree(tmp_path, scripts={"agent_profile_sync.py": body})

    # When / Then  it passes — the mtime fact is evidence, not an ownership guess
    assert rh.findings(root) == []


def test_comment_and_docstring_quoting_the_phrase_are_not_reporting(tmp_path: Path):
    """A comment/docstring that QUOTES a forbidden phrase to explain the rule is not reporting output.

    `agent_profile_sync.py`'s own comment says "'another lane's work' was a guess the harness had no
    right to make" — that is the corrected principle, scoped to the rule, and must not red.
    """

    # Given a leg that only QUOTES the phrase in a comment/docstring (never emits it)
    body = (
        '"""the tree has no ownership information, so never say whose work it is; "\n'
        '"\'another lane\'s work\' was a guess the harness had no right to make."""\n'
        'def f():\n'
        '    # the live file was edited AFTER the tree copy was committed\n'
        '    return 1\n'
    )
    root = _tree(tmp_path, scripts={"agent_profile_sync.py": body})

    # When / Then  no violation — comments and docstrings are not reporting legs
    assert rh.findings(root) == []


def test_whole_repo_is_green():
    """The guard passes over THIS repository — a convention the repo itself violates is not one."""

    assert rh.findings(REPO) == []


def test_exit_code_matters():
    """`make check-report-hygiene` runs in ci-unit, so main() must return 1 on a violation, 0 here."""

    assert rh.main(["check"]) == 0
