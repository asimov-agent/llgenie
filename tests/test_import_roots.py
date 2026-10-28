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


def test_the_ratchet_passes_at_the_recorded_count_and_refuses_an_increase(tmp_path):
    root = tree(tmp_path, {"tests/test_x.py": "import sys\nsys.path.insert(0, 'scripts')\n"})
    (root / "tests" / "fixtures").mkdir()
    (root / guard.BASELINE).write_text(json.dumps({"sys-path": 1, "bare": 0, "syntax": 0}))
    assert guard.ratchet(root) == []

    (root / "tests" / "test_new.py").write_text("import sys\nsys.path.insert(0, 'scripts')\n")
    items = guard.ratchet(root)
    assert [i["key"] for i in items] == ["sys-path"]
    assert "may only shrink" in items[0]["detail"]


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
