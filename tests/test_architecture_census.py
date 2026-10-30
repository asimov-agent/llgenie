"""The census gate's referent is the tree at the doc's `measured at <sha>`, never HEAD (issue #1053).

`docs/ARCHITECTURE.md` states a census of the tree next to a `measured at <sha>` pointer. A census is
a claim about ONE commit, so that commit is what the gate must count: a branch that adds a file does
not have to rewrite the doc, and the pointer does not dangle once the PR is squashed. The pointer
still has to be a real commit this branch contains (an ancestor of HEAD), and a doc whose numbers
disagree with the tree at that sha still fails.

Driven through a REAL scratch git repository — the thing under test *is* git plumbing — and the
module's only stand-in is its checkout path (`REPO_ROOT`), so the real `git ls-tree` still runs.
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parent.parent
GATE = REPO / "scripts" / "check_architecture_census.py"

COUNTED_DIRS = ("data", "skills", "containers", "tests", "scripts", "openspec", "agent-wiki", "docs")


def git(*args: str, cwd: Path) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    assert r.returncode == 0, f"git {' '.join(args)} failed: {r.stderr}"
    return r.stdout.strip()


def ls_names(where: Path, ref: str, path: str = "") -> list[str]:
    cmd = ["ls-tree", "-r", "--name-only", ref]
    if path:
        cmd += ["--", path]
    return [l for l in git(*cmd, cwd=where).split("\n") if l]


def census_text(where: Path, sha: str) -> str:
    """A census sentence + cells stating the REAL counts of `sha`, computed with git itself."""
    counts = {d: len(ls_names(where, sha, d)) for d in COUNTED_DIRS}
    tests = ls_names(where, sha, "tests")
    test_py = len([n for n in tests
                   if n.rsplit("/", 1)[-1].startswith("test_") and n.endswith(".py")])
    changes = len({n.split("/")[2] for n in ls_names(where, sha, "openspec/changes")})
    return (
        f"The tree is {len(ls_names(where, sha))} tracked files: `data/` {counts['data']}, "
        f"`skills/` {counts['skills']}, `containers/` {counts['containers']}, "
        f"`tests/` {counts['tests']}, `scripts/` {counts['scripts']}, "
        f"`openspec/` {counts['openspec']}, `agent-wiki/` {counts['agent-wiki']} and "
        f"`docs/` {counts['docs']}. ({changes} changes) ({counts['agent-wiki']} entries) "
        f"{test_py} `tests/test_*.py` (measured at `{sha}`).\n"
    )


def load_gate(where: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_architecture_census_under_test", GATE)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    setattr(mod, "REPO_ROOT", where)   # the only stand-in: which checkout the real git runs in
    return mod


def write_doc(where: Path, text: str) -> None:
    (where / "docs").mkdir(exist_ok=True)
    (where / "docs" / "ARCHITECTURE.md").write_text(text, encoding="utf-8")


def commit_all(where: Path, message: str) -> str:
    git("add", "-A", cwd=where)
    git("commit", "-q", "-m", message, cwd=where)
    return git("rev-parse", "HEAD", cwd=where)


def scratch_repo(tmp_path: Path) -> tuple[Path, str, str]:
    """A real repo: commit1 holds the tree the census names; commit2 adds the doc; commit3 adds a file."""

    where = tmp_path / "repo"
    where.mkdir()
    git("init", "-q", "-b", "main", cwd=where)
    git("config", "user.name", "Andy Holst", cwd=where)
    git("config", "user.email", "andy.holst@protonmail.com", cwd=where)
    git("config", "commit.gpgsign", "false", cwd=where)

    for rel, body in {
        "data/models.json": "{}\n",
        "skills/engines/demo/SKILL.md": "# demo\n",
        "containers/engines/dockerfiles/demo/Dockerfile.cpu": "FROM scratch\n",
        "tests/test_demo.py": "def test_demo():\n    assert True\n",
        "scripts/demo.py": "print('demo')\n",
        "openspec/changes/demo/tasks.md": "- [x] demo\n",
        "agent-wiki/2026-01-01-demo.md": "# demo\n",
        "docs/other.md": "# other\n",
        "README.md": "# repo\n",
    }.items():
        path = where / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")

    base = commit_all(where, "the tree the census is measured on")
    write_doc(where, census_text(where, base))
    doc_commit = commit_all(where, "the architecture doc, census measured at the base tree")
    (where / "extra.txt").write_text("a file this branch adds\n", encoding="utf-8")
    head = commit_all(where, "a file added after the census was measured")
    return where, base, head


def test_a_branch_that_adds_files_does_not_have_to_move_the_census(tmp_path, capsys):
    """The counts are read at the doc's pointer, so new files after it are not a drift (issue #1053)."""

    # Given a branch whose doc census was measured at an ancestor, and files added since
    where, base, head = scratch_repo(tmp_path)
    gate = load_gate(where)
    assert ls_names(where, head) != ls_names(where, base)          # the branch really added files
    assert gate.doc_measured_sha() == base

    # When  the gate runs at that branch head
    rc = gate.check()

    # Then  it passes, and it reports the pointer it measured, not HEAD
    out = capsys.readouterr().out
    assert rc == 0, out
    assert f"census measured at `{base}`" in out
    assert gate.measure(base)["tracked"] == len(ls_names(where, base))
    assert gate.measure(base)["tracked"] != gate.measure()["tracked"]


def test_a_stale_number_reds_naming_the_claim(tmp_path, capsys):
    """A doc number that disagrees with the tree AT THE POINTER still fails, naming both values."""

    # Given a doc whose `data/` count is one too high for the tree at its own pointer
    where, base, _ = scratch_repo(tmp_path)
    real = len(ls_names(where, base, "data"))
    text = census_text(where, base).replace(f"`data/` {real}", f"`data/` {real + 1}")
    write_doc(where, text)
    gate = load_gate(where)

    # When  the gate runs
    rc = gate.check()

    # Then  it exits non-zero and names BOTH values — what the doc says and what the tree states
    out = capsys.readouterr().out
    assert rc == 1, out
    assert f"data: the doc states {real + 1} but the tree at `{base}` states `data/` {real}" in out
    assert "1 claim(s) stale" in out


def test_a_pointer_to_a_non_ancestor_commit_reds_naming_it(tmp_path, capsys):
    """A real commit this branch does not contain cannot be the referent (#1043's remaining half)."""

    # Given a real commit object that is not an ancestor of HEAD
    where, _, _ = scratch_repo(tmp_path)
    tree = git("rev-parse", "HEAD^{tree}", cwd=where)
    orphan = git("commit-tree", tree, "-m", "an orphan commit", cwd=where)
    assert gate_is_real(where, orphan)
    doc = (where / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    write_doc(where, doc.replace(doc_measured(doc), orphan))
    gate = load_gate(where)

    # When  the gate runs
    rc = gate.check()

    # Then  it exits non-zero and names the sha it refuses
    out = capsys.readouterr().out
    assert rc == 1, out
    assert f"`{orphan}` is not an ancestor of HEAD" in out


def test_a_dangling_pointer_reds(tmp_path, capsys):
    """A sha from an amended-away commit is not a referent anyone can reproduce."""

    # Given a pointer to a sha that exists nowhere in the repo
    where, _, _ = scratch_repo(tmp_path)
    doc = (where / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    dangling = "0123456789abcdef0123456789abcdef01234567"
    write_doc(where, doc.replace(doc_measured(doc), dangling))
    gate = load_gate(where)

    # When  the gate runs
    rc = gate.check()

    # Then  it exits non-zero, saying the commit is not real
    out = capsys.readouterr().out
    assert rc == 1, out
    assert f"`{dangling}` is not a real commit" in out


def test_a_doc_with_no_pointer_reds(tmp_path, capsys):
    """The pointer is the referent; a doc without one has no census a reader can check."""

    # Given a census with no `measured at <sha>` pointer
    where, base, _ = scratch_repo(tmp_path)
    write_doc(where, census_text(where, base).replace(f" (measured at `{base}`)", ""))
    gate = load_gate(where)

    # When  the gate runs
    rc = gate.check()

    # Then  it exits non-zero and asks for the pointer
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "docs/ARCHITECTURE.md states no `measured at <sha>` pointer" in out


def gate_is_real(where: Path, sha: str) -> bool:
    r = subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=where,
                       capture_output=True, text=True)
    return r.returncode == 0


def doc_measured(text: str) -> str:
    import re
    found = re.search(r"measured at `([0-9a-f]{7,})`", text)
    assert found, "the fixture doc states no measured-at pointer"
    return found.group(1)
