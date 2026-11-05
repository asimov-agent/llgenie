"""The report-header guard (issue #1615): an emitted status header is a full six-field report or nothing.

The fleet report contract demands every report carry the same-pass evidence the header exists to
tie: `BOT <name> · working on #<id> · branch <ref> · since <hh:mmZ> · blocked on <x|none> · next <y>`.
This guard scans the reporting legs (emitted strings in `scripts/*.py` — docstrings excluded — and
workflow `name:`/`run:` lines) and fails on any emitted line that carries a header signal without
carrying ALL six fields with concrete values.

The tests pin the contract from both sides:
- a stubbed status header *without* one field (say `blocked on`) must red, and the same header
  *with* the full six fields must pass (the acceptance criterion);
- a `working on #<id>` placeholder (a rule statement describing a header) must NOT satisfy the
  contract — a template resolves no same-pass id;
- a negative control: a fixture reporting leg that emits a `BOT ... working on #12` partial header
  reds the check, while a plain echo (`print("hello")`) never scans;
- the tree's own scans pass: the guard over the WHOLE repository stays green because no leg emits a
  partial status header, and the reported status line itself is emitted only under the full grammar.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

from pathlib import Path

from scripts import check_report_header as rh

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


FULL = ("BOT demo-lane · working on #1234 · branch fix/thing · since 21:30Z · "
        "blocked on none · next push")


def test_full_header_passes(tmp_path: Path):
    """The complete six-field status header is the contract and must pass unchanged."""
    root = _tree(tmp_path, scripts={"a.py": f"print({FULL!r})\n"})
    assert rh.findings(root) == []


def test_missing_blocked_on_field_is_a_violation(tmp_path: Path):
    """A status header that drops `blocked on` is a stale self-report and must red."""
    header = "BOT demo-lane · working on #1234 · branch fix/thing · since 21:30Z · next push"
    root = _tree(tmp_path, scripts={"a.py": f"print({header!r})\n"})
    items = rh.findings(root)
    keys = [f["key"] for f in items]
    assert any("partial-header" in k for k in keys)
    assert any("blocked on" in f["title"] for f in items)


def test_missing_id_is_a_violation(tmp_path: Path):
    """A report without an issue id is explicitly 'not a report' — it must red."""
    header = ("BOT demo-lane · branch fix/thing · since 21:30Z · blocked on none · next push")
    root = _tree(tmp_path, scripts={"a.py": f"print({header!r})\n"})
    assert rh.findings(root)


def test_working_on_placeholder_does_not_resolve(tmp_path: Path):
    """A `working on #<id>` template is a RULE description, not a same-pass id — it reds.

    A reporting surface that says `working on #<id>` is teaching the grammar, not asserting a real
    id. Accepting it would let a leg describe the header instead of emitting it.
    """
    header = ("BOT demo-lane · working on #<id> · branch fix/thing · since 21:30Z · "
              "blocked on none · next push")
    root = _tree(tmp_path, scripts={"a.py": f"print({header!r})\n"})
    assert rh.findings(root)


def test_empty_or_plain_echo_never_scans(tmp_path: Path):
    """A line with no header signal (a plain echo) is not reporting and must not red."""
    root = _tree(tmp_path, scripts={"a.py": 'print("hello there")\n'})
    assert rh.findings(root) == []


def test_docstring_quoting_the_header_is_not_reporting(tmp_path: Path):
    """A comment/docstring that QUOTES a partial header to explain the rule is not reporting output.

    `check_report_header.py`'s own docstring quotes an example — that documents the rule, it is not
    a status emission, and must not red.
    """
    body = (
        '"""the contract is `BOT <name> · working on #<id> · branch <ref> · since <hh:mmZ> · "\n'
        '"blocked on <x|none> · next <y>`, never a partial `BOT x · working on #12`."""\n'
        "def f():\n    return 1\n"
    )
    root = _tree(tmp_path, scripts={"a.py": body})
    assert rh.findings(root) == []


def test_workflow_run_partial_header_reds(tmp_path: Path):
    """The negative control reaches workflow legs too — a run: header missing a field reds."""
    root = _tree(tmp_path, workflow=(
        "jobs:\n  j:\n    runs-on: ubuntu\n    steps:\n"
        "      - run: \"BOT demo-lane · working on #9 · branch fix/thing\"\n"
    ))
    assert rh.findings(root)


def test_keywords_alone_are_not_a_header_signal(tmp_path: Path):
    """Bare field keywords without a status shape are not a header and must not scan.

    A prose line that happens to contain `branch` and `next` words is not a status emission.
    """
    root = _tree(tmp_path, scripts={"a.py": 'print("branch the next thing here")\n'})
    assert rh.findings(root) == []


def test_whole_repo_is_green():
    """The guard passes over THIS repository — a convention the repo itself violates is not one."""

    assert rh.findings(REPO) == []


def test_exit_code_matters():
    """`make check-report-header` runs in ci-unit, so main() must return 1 on a violation, 0 here."""

    assert rh.main(["check"]) == 0
