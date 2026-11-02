"""Zero-byte file gate (issue #1509): the tripwire's absence must never recur.

`.wt-probe.txt` — a 0-byte blob `e69de29b` — rode a squash (#1467) to `main` because
no target rejected empty files. These tests hold the gate's two seams:

1. a zero-byte path the change set *adds* (`base...HEAD`) is refused, naming it;
2. a `.gitkeep`-style sentinel is the *only* allowed empty file;
3. an explicit `--allow` entry exempts a named path;
4. `--all` extends the gate to every *present* empty tracked file;
5. clean trees pass.

Each test builds a tiny real git repo (the gate reads `git ls-files`/`git diff`), so a
".gitkeep" fixture exercises the allow-list rather than an empty working tree faking it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from scripts import check_empty_files as gate


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def make_repo(tmp_path: Path, files: dict[str, bytes]) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "base")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    for name, data in files.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    return root


def _commit(root: Path, files: dict[str, bytes], msg: str = "change") -> None:
    for name, data in files.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    _git(root, "add", ".")
    _git(root, "commit", "-qm", msg)


def _head_sha(root: Path) -> str:
    return subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()


def test_an_added_zero_byte_non_sentinel_file_is_refused(tmp_path):
    root = make_repo(tmp_path, {"a.txt": b"x"})
    _commit(root, {".wt-probe.txt": b""})
    head = _head_sha(root)
    items = gate.findings(root, base=head + "~1")
    assert [i["where"] for i in items] == [".wt-probe.txt"]
    assert "ADDED EMPTY" in items[0]["detail"]
    assert gate.render(items).startswith("[check-empty-files] 1 empty-file path(s):")


def test_a_change_that_adds_only_non_empty_files_passes(tmp_path):
    root = make_repo(tmp_path, {"base.txt": b"x"})
    _commit(root, {"a.txt": b"data"})
    head = _head_sha(root)
    assert gate.findings(root, base=head + "~1") == []


def test_a_missing_base_means_nothing_to_gate(tmp_path):
    root = make_repo(tmp_path, {"a.txt": b"x"})
    assert gate.findings(root) == []           # no base -> no added-paths to refuse


def test_a_gitkeep_sentinel_is_the_allowed_empty_case(tmp_path):
    root = make_repo(tmp_path, {"data/.gitkeep": b""})
    assert gate.findings(root, all_tracked=True) == []


def test_a_present_empty_non_sentinel_is_refused_only_with_all(tmp_path):
    root = make_repo(tmp_path, {"x.txt": b"data", "empty.txt": b""})
    assert gate.findings(root) == []                       # base-absent: nothing added
    items = gate.findings(root, all_tracked=True)
    assert [i["where"] for i in items] == ["empty.txt"]
    assert "present" in items[0]["key"]


def test_an_explicit_allow_entry_exempts_a_named_path(tmp_path):
    root = make_repo(tmp_path, {"x.txt": b"data", "sentinel.txt": b""})
    assert gate.findings(root, all_tracked=True, allow=("sentinel.txt",)) == []


def test_a_clean_repo_passes_in_both_modes(tmp_path):
    root = make_repo(tmp_path, {"a.txt": b"data", "docs/.gitkeep": b""})
    _commit(root, {"b.txt": b"more"})
    head = _head_sha(root)
    assert gate.findings(root, base=head + "~1") == []
    assert gate.findings(root, all_tracked=True) == []
    assert gate.render([]) == ("[check-empty-files] OK: no zero-byte non-sentinel file "
                               "(added or present)")


def test_main_check_via_the_pr_gate_is_clean_post_removal(tmp_path):
    """The acceptance: a PR gate run on a tree without empty files reports zero paths."""
    root = make_repo(tmp_path, {"a.txt": b"data"})
    assert gate.findings(root, all_tracked=True) == []
