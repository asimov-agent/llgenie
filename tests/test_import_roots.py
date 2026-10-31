"""The import-root guard (issue #796): both rules, both directions, and the ratchet.

A guard that lands on a tree with 104 path entries cannot be a plain gate — it would red the suite on
the commit that adds it — so the shipped mode is a ratchet: the count may fall as batches migrate and
may never rise. These tests hold the two rules and the ratchet's two directions.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import check_import_roots as guard

REPO = Path(__file__).resolve().parent.parent


def tree(tmp_path: Path, files: dict[str, str]) -> Path:
    root = tmp_path / "repo"
    (root / "tests").mkdir(parents=True)
    (root / "scripts").mkdir()
    (root / "scripts" / "hf_auth.py").write_text("x = 1\n")
    for name, body in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
    return root


def test_a_path_entry_outside_the_conftest_is_refused(tmp_path):
    root = tree(tmp_path, {"tests/test_x.py": "import sys\nsys.path.insert(0, 'scripts')\n"})
    items = guard.findings(root)
    assert [i["key"] for i in items] == ["sys-path"]
    assert items[0]["where"].endswith("tests/test_x.py:2")


def test_the_conftest_is_the_one_file_allowed_to_add_a_root(tmp_path):
    root = tree(tmp_path, {"tests/conftest.py": "import sys\nsys.path.insert(0, 'scripts')\n"})
    assert guard.findings(root) == []


def test_a_scripts_module_imported_bare_is_refused(tmp_path):
    root = tree(tmp_path, {"tests/test_y.py": "import hf_auth\n"})
    items = guard.findings(root)
    assert [i["key"] for i in items] == ["bare"]
    assert "scripts.hf_auth" in items[0]["detail"]


def test_the_same_module_imported_through_the_package_is_clean(tmp_path):
    root = tree(tmp_path, {"tests/test_z.py": "from scripts.hf_auth import x\n"})
    assert guard.findings(root) == []


def test_a_file_that_does_not_parse_is_its_own_finding(tmp_path):
    root = tree(tmp_path, {"tests/test_bad.py": "def (:\n"})
    assert [i["key"] for i in guard.findings(root)] == ["syntax"]


def test_the_ratchet_passes_at_the_recorded_set_and_refuses_an_added_root(tmp_path):
    root = tree(tmp_path, {"tests/test_x.py": "import sys\nsys.path.insert(0, 'scripts')\n"})
    (root / "tests" / "fixtures").mkdir()
    (root / guard.BASELINE).write_text(_set_baseline({"sys-path": ["tests/test_x.py:2"]}))
    assert guard.ratchet(root) == []

    (root / "tests" / "test_new.py").write_text("import sys\nsys.path.insert(0, 'scripts')\n")
    items = guard.ratchet(root)
    assert [i["key"] for i in items if i.get("new")] == ["sys-path"]
    assert [i["new"] for i in items if i.get("new")] == [["tests/test_new.py:2"]]


def test_the_ratchet_refuses_a_missing_baseline_rather_than_passing_silently(tmp_path):
    root = tree(tmp_path, {"tests/test_x.py": "x = 1\n"})
    items = guard.ratchet(root)
    assert items and items[0]["key"] == "baseline"


def test_the_cli_exit_codes_both_ways(tmp_path):
    clean = tree(tmp_path / "a", {"tests/test_ok.py": "from scripts.hf_auth import x\n"})
    assert guard.main(["check", "--root", str(clean)]) == 0

    dirty = tree(tmp_path / "b", {"tests/test_bad.py": "import hf_auth\n"})
    assert guard.main(["check", "--root", str(dirty)]) == 1


def test_an_insert_inside_a_test_body_is_not_a_finding(tmp_path):
    """A test that builds a temporary plugin tree inserts THAT path; removing it breaks the test, not the seam.

    Measured on `tests/test_agent_nerve.py`: the migration stripped `sys.path.insert(0, str(home / "plugins"
    / "nerve"))` from inside the test and the case failed with `No module named 'hermes_nerve'` — the rule
    is about the module-level bootstrap, so the guard reads the AST and only flags module-level inserts.
    """
    root = tree(tmp_path, {"tests/test_plugin.py": (
        "import sys\n"
        "def test_x(tmp_path):\n"
        "    sys.path.insert(0, str(tmp_path / 'plugins'))\n"
        "    assert True\n")})
    assert guard.findings(root) == []


def test_a_module_level_insert_is_still_a_finding(tmp_path):
    root = tree(tmp_path, {"tests/test_boot.py": "import sys\nsys.path.insert(0, 'scripts')\n"})
    items = guard.findings(root)
    assert [i["key"] for i in items] == ["sys-path"]
    assert "module-level" in items[0]["detail"]


def test_the_guard_says_a_baseline_is_a_measurement_and_not_a_constant():
    """The lesson from re-cutting this branch belongs in the guard, not in a PR comment.

    The baseline read `34 bare / 14 sys-path` at cut and `107 / 151` on `main` two hours later, because
    other lanes added tests that bootstrap their own path. Recorded as-is, the guard would have been red on
    `main` itself — so the docstring has to say that a baseline is re-recorded at what the branch produces,
    or the next lane copies the number and inherits the contradiction.
    """
    doc = " ".join((guard.__doc__ or "").lower().split())
    for phrase in ["a baseline is a measurement, not a constant",
                   "re-record at what the branch actually produces",
                   "it may fall, never rise"]:
        assert phrase in doc, f"the guard does not document the ratchet's first rule: {phrase}"


def _set_baseline(recorded: dict[str, list[str]]) -> str:
    """A set-shaped baseline: each rule records its counted `file:line` sites and the aggregate."""
    return json.dumps({k: {"count": len(v), "sites": sorted(v)} for k, v in recorded.items()},
                      indent=2, sort_keys=True)


def _ratchet_tree(tmp_path: Path, files: dict[str, str], recorded: dict[str, list[str]]) -> Path:
    """A real tree with a committed set-shaped baseline, so the ratchet runs exactly as CI runs it."""
    root = tree(tmp_path, files)
    (root / "tests" / "fixtures").mkdir()
    (root / guard.BASELINE).write_text(_set_baseline(recorded))
    return root


def test_the_ratchet_refusal_names_exactly_the_new_file_and_line(tmp_path, capsys):
    """The refusal is a set difference: it names the ONE new root, not every site the rule counted (#1101).

    Measured on `main@769964a1` after #1066: the output listed all 33 `sys-path` sites and the
    assertion claimed the offender was "among them" — a reader who did not add it must still diff the
    list. Set-shaped, the ratchet names exactly the site present now and absent at the baseline.
    """

    # Given a tree at its recorded set, and a new test file that adds its own module-level root
    root = _ratchet_tree(tmp_path, {"tests/test_x.py": "import sys\nsys.path.insert(0, 'scripts')\n"},
                         {"sys-path": ["tests/test_x.py:2"], "bare": [], "syntax": []})
    (root / "tests" / "test_new.py").write_text("import sys\nsys.path.insert(0, 'scripts')\n")

    # When  the ratchet runs
    items = guard.ratchet(root)
    code = guard.main(["ratchet", "--root", str(root)])
    named = capsys.readouterr().err

    # Then  it refuses, naming that exact file and line — and never the recorded one alongside it
    assert code == 1
    assert [i["new"] for i in items if i.get("new")] == [["tests/test_new.py:2"]]
    assert "tests/test_new.py:2" in named
    assert "tests/test_x.py:2" not in named


def test_the_ratchet_is_green_and_names_no_site_when_nothing_was_added(tmp_path, capsys):
    """Negative control: at the recorded set the gate is silent about sites and exits 0."""

    # Given a tree whose current set equals its baseline
    root = _ratchet_tree(tmp_path, {"tests/test_x.py": "import sys\nsys.path.insert(0, 'scripts')\n"},
                         {"sys-path": ["tests/test_x.py:2"], "bare": [], "syntax": []})

    # When  the ratchet runs
    code = guard.main(["ratchet", "--root", str(root)])
    out = capsys.readouterr().out

    # Then  it passes, and prints no site
    assert code == 0
    assert "tests/test_x.py:2" not in out


def test_the_ratchet_reports_a_removed_root_as_the_allowed_shrink(tmp_path, capsys):
    """The count may only shrink: removing a root is green AND reports which one went (issue #796)."""

    # Given a tree missing one of the two recorded roots
    root = _ratchet_tree(tmp_path, {"tests/test_x.py": "import sys\nsys.path.insert(0, 'scripts')\n"},
                         {"sys-path": ["tests/test_x.py:2", "tests/test_y.py:1"], "bare": [], "syntax": []})

    # When  the ratchet runs
    code = guard.main(["ratchet", "--root", str(root)])

    # Then  it passes, and names the shrunken site as allowed
    assert code == 0
    out = capsys.readouterr().out
    assert "tests/test_y.py:1" in out
    assert "allowed" in out


def test_a_legacy_count_baseline_still_ratchets(tmp_path, capsys):
    """A pre-#1101 count-shaped entry still refuses an overshoot and says to re-record once."""

    # Given a baseline whose sys-path entry is a plain integer
    root = tree(tmp_path, {"tests/test_x.py": "import sys\nsys.path.insert(0, 'scripts')\n",
                           "tests/test_y.py": "import sys\nsys.path.insert(0, 'scripts')\n"})
    (root / "tests" / "fixtures").mkdir()
    (root / guard.BASELINE).write_text(json.dumps({"sys-path": 1, "bare": 0, "syntax": 0}))

    # When  the ratchet runs
    code = guard.main(["ratchet", "--root", str(root)])
    named = capsys.readouterr().err

    # Then  it refuses, names the sites it cannot split, and says to re-record once
    assert code == 1
    assert "re-record" in named
    assert "tests/test_x.py:2" in named and "tests/test_y.py:2" in named


def test_report_still_lists_every_finding_and_exits_zero(tmp_path, capsys):
    """`report` is unchanged by the ratchet's new detail: same lines, same exit code (issue #1066)."""

    # Given a tree with one bare scripts/ import
    root = tree(tmp_path, {"tests/test_y.py": "import hf_auth\n"})

    # When  report runs
    code = guard.main(["report", "--root", str(root)])
    out = capsys.readouterr().out

    # Then  it names that file:line and exits 0
    assert code == 0
    assert "tests/test_y.py:1" in out
