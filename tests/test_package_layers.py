"""The scripts/ layering gate (issue #795): data + gate + the cycle it was filed for.

Spec: `openspec/changes/scripts-package-layers/specs/scripts-package-layers/spec.md`.

Every refusal is proven against a TEMP COPY of the tree the test builds itself — a real
`scripts/` package, a real `package-layers.json`, a real §Scripts table — because a gate
asserted only against today's clean tree would pass with every rule deleted.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import check_package_layers as cpl

REPO_ROOT = Path(__file__).resolve().parent.parent


def _tree(tmp_path: Path, files: dict[str, str], groups: dict[str, list[str]],
          allowed: list[dict] | None = None) -> Path:
    """A minimal but REAL tree: a `scripts/` package, its layering data and the §Scripts table."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "__init__.py").write_text("", encoding="utf-8")
    for name, body in files.items():
        (tmp_path / "scripts" / f"{name}.py").write_text(body, encoding="utf-8")
    data = {"groups": groups, "allowed_edges": allowed or []}
    (tmp_path / "scripts" / "package-layers.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
    rows = "\n".join(f"| {group} | " + ", ".join(f"`{m}.py`" for m in modules) + " |"
                     for group, modules in groups.items())
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "ARCHITECTURE.md").write_text(
        "## Scripts\n\n| Group | Modules |\n|---|---|\n" + rows + "\n\n## Next\n", encoding="utf-8")
    return tmp_path


def _keys(root: Path) -> list[str]:
    return [item["key"] for item in cpl.findings(root)]


def _run(root: Path, command: str = "check") -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "check_package_layers.py"),
                           command, "--root", str(root)],
                          capture_output=True, text=True, cwd=REPO_ROOT)


def test_the_repository_tree_passes_its_own_layering_gate():
    """The committed data and the committed tree agree — the gate is green where it is wired."""

    # Given the real checkout
    root = REPO_ROOT

    # When  the gate runs over it
    result = _run(root)

    # Then  it exits 0 and says so
    assert result.returncode == 0, result.stdout + result.stderr
    assert "check-package-layers: OK" in result.stdout


def test_the_data_file_names_every_module_of_the_tree():
    """Acceptance: `scripts/package-layers.json` names every module in `scripts/`."""

    # Given the committed layering data and the real tree
    data = json.loads((REPO_ROOT / "scripts" / "package-layers.json").read_text(encoding="utf-8"))
    placed = {name for modules in data["groups"].values() for name in modules}
    modules = cpl.script_modules(REPO_ROOT)

    # When  the two sets are compared
    missing, unknown = sorted(modules - placed), sorted(placed - modules)

    # Then  they are the same set — no module unplaced, no placement the tree lost
    assert missing == [], f"modules with no group: {missing}"
    assert unknown == [], f"grouped modules the tree does not have: {unknown}"


def test_a_new_cycle_is_fatal(tmp_path):
    """A cycle between two modules of the SAME group is refused: the layering never legalises one."""

    # Given two modules that import each other inside one group
    root = _tree(tmp_path, {"a": "from . import b\n", "b": "import a\n"},
                 {"Alpha": ["a", "b"]})

    # When  the gate reads the tree
    keys = _keys(root)

    # Then  it names the cycle, whatever the group border says
    assert "cycle" in keys


def test_a_function_local_import_is_an_edge(tmp_path):
    """The shape the issue was filed for: a reverse import hidden inside a function is still a cycle."""

    # Given a cycle whose reverse edge sits inside a function body
    root = _tree(tmp_path, {"a": "from . import b\n",
                            "b": "def f():\n    from . import a\n    return a\n"},
                 {"Alpha": ["a", "b"]})

    # When  the gate reads the tree
    keys = _keys(root)

    # Then  the hidden edge is counted and the cycle is refused
    assert "cycle" in keys


def test_a_cross_group_import_absent_from_the_file_is_fatal(tmp_path):
    """Acceptance (b): a cross-border import that the data does not state is a red gate."""

    # Given a module importing across a border with no `allowed_edges` entry
    root = _tree(tmp_path, {"a": "from . import b\n", "b": "x = 1\n"},
                 {"Alpha": ["a"], "Beta": ["b"]})

    # When  the gate reads the tree
    keys = _keys(root)

    # Then  the crossing is refused as unstated
    assert "cross-group" in keys
    assert _run(root).returncode == 1


def test_a_stated_cross_group_edge_is_allowed(tmp_path):
    """The positive half: the same import, declared with its reason, is green."""

    # Given the same crossing, now stated in the data with a reason
    root = _tree(tmp_path, {"a": "from . import b\n", "b": "x = 1\n"},
                 {"Alpha": ["a"], "Beta": ["b"]},
                 allowed=[{"from": "a", "to": "b", "reason": "a reads b's one definition"}])

    # When  the gate reads the tree
    result = _run(root)

    # Then  it exits 0
    assert result.returncode == 0, result.stdout + result.stderr


def test_an_allowlisted_edge_that_no_longer_exists_is_fatal(tmp_path):
    """Acceptance (c): the file cannot rot — an exception outliving its import is refused."""

    # Given a stated edge the tree no longer contains
    root = _tree(tmp_path, {"a": "x = 1\n", "b": "x = 1\n"},
                 {"Alpha": ["a"], "Beta": ["b"]},
                 allowed=[{"from": "a", "to": "b", "reason": "was once a real edge"}])

    # When  the gate reads the tree
    keys = _keys(root)

    # Then  the stale entry is named
    assert "stale-edge" in keys


def test_an_allowlisted_edge_needs_a_reason(tmp_path):
    """An unstated exception is the review opinion this gate replaces, so it is refused."""

    # Given a stated edge with no reason
    root = _tree(tmp_path, {"a": "from . import b\n", "b": "x = 1\n"},
                 {"Alpha": ["a"], "Beta": ["b"]},
                 allowed=[{"from": "a", "to": "b", "reason": "  "}])

    # When  the gate reads the tree
    keys = _keys(root)

    # Then  the entry is refused
    assert "stale-edge" in keys


def test_a_module_the_file_does_not_place_is_fatal(tmp_path):
    """Acceptance: the gate fails on a module it does not know."""

    # Given a module of `scripts/` that no group holds
    root = _tree(tmp_path, {"a": "x = 1\n", "orphan": "x = 1\n"}, {"Alpha": ["a"]})

    # When  the gate reads the tree
    keys = _keys(root)

    # Then  the unplaced module is named
    assert "unknown-module" in keys


def test_a_placement_the_tree_lost_is_fatal(tmp_path):
    """The other direction: the data cannot describe a module that is gone."""

    # Given a group naming a module the tree does not have
    root = _tree(tmp_path, {"a": "x = 1\n"}, {"Alpha": ["a", "gone"]})

    # When  the gate reads the tree
    keys = _keys(root)

    # Then  the lost module is named
    assert "missing-module" in keys


def test_a_module_in_two_groups_is_fatal(tmp_path):
    """A module belongs to exactly one group; the last one silently winning is a defect."""

    # Given a module placed in two groups
    root = _tree(tmp_path, {"a": "x = 1\n"}, {"Alpha": ["a"], "Beta": ["a"]})

    # When  the gate reads the tree
    keys = _keys(root)

    # Then  the duplication is named
    assert "duplicate-module" in keys


def test_unreadable_data_is_exit_2_never_a_pass(tmp_path):
    """A gate that cannot read its data must not look like a clean tree."""

    # Given a tree whose layering file is missing
    root = _tree(tmp_path, {"a": "x = 1\n"}, {"Alpha": ["a"]})
    (root / "scripts" / "package-layers.json").unlink()

    # When  the gate runs
    result = _run(root)

    # Then  it exits 2 (unreadable), not 0
    assert result.returncode == 2


def test_derive_imports_without_engine_bump():
    """Acceptance: `import scripts.engine_params_derive` no longer drags in `engine_bump`."""

    # Given a fresh interpreter importing the derive pipeline
    probe = ("import sys, scripts.engine_params_derive\n"
             "print('scripts.engine_bump' in sys.modules)\n")
    result = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, cwd=REPO_ROOT)

    # When  it reports what the import pulled in
    lines = result.stdout.split()

    # Then  engine_bump is not among it, and the import itself succeeded
    assert result.returncode == 0, result.stderr
    assert lines == ["False"], result.stdout


def test_engine_bump_still_imports_and_runs_its_cli():
    """The bump pipeline keeps its public surface (the moved step is re-exported, not lost)."""

    # Given the bump module's CLI
    result = subprocess.run([sys.executable, "scripts/engine_bump.py", "--help"],
                            capture_output=True, text=True, cwd=REPO_ROOT)

    # When  it runs
    # Then  it prints its usage and exits 0
    assert result.returncode == 0, result.stderr
    assert "bump-daily" in result.stdout


def test_the_moved_release_step_is_the_same_one_engine_bump_exports():
    """The cycle was broken by moving a step, not by copying it: one owner, re-exported."""

    # Given the two modules
    from scripts import engine_bump as eb
    from scripts import engine_release_archive as era

    # When  the names are compared
    # Then  engine_bump's surface IS the moved module's functions
    assert eb._release_assets is era._release_assets
    assert eb._native_archives is era._native_archives
    assert eb.release_archive_install is era.release_archive_install


def test_the_doc_names_the_file_and_the_target():
    """Acceptance: §Scripts names the data file and the make target beside the group table."""

    # Given the architecture document's §Scripts section
    text = (REPO_ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    section = text.split("## Scripts", 1)[1].split("\n## ", 1)[0]

    # When  it is searched for the seam
    # Then  both the data file and the gate target are stated there
    assert "scripts/package-layers.json" in section
    assert "check-package-layers" in section


if __name__ == "__main__":                                    # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
