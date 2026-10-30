"""The rebase lane's shipped scripts must be executable and syntactically clean.

Why this exists: the two scripts under
`agents/llgenie-pr-merge-conflict/skills/llgenie-pr-rebase/scripts/` were correctness-critical
gates for every rebase push, and they were only ever exercised from the live profile. When the
tree copy was finally run, `post-rebase-verify.sh` printed `base=refs/rem` — it misreported the
base it had verified against, because `${BASE:0:8}` truncates a ref instead of resolving it.
Nothing in the tree would have caught that: a script can ship non-executable, or with a syntax
error, and every gate stays green because no gate reads it.

Scope is deliberately THIS LANE ONLY. Asserting over all agent skills would red another lane's
work the moment one of its scripts is legitimately mid-edit, and a test that punishes a correct
change teaches the next person to edit the test. A lane that wants its own scripts covered adds
its own case here.
"""
from __future__ import annotations

import ast
import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = (REPO / "agents" / "llgenie-pr-merge-conflict" / "skills"
           / "llgenie-pr-rebase" / "scripts")

# Subset check, never equality: the lane is meant to add scripts, and an exact list would red
# on the next legitimate addition.
EXPECTED = {"post-rebase-verify.sh", "salvage-audit.sh", "salvage-four-bucket.py"}


def _shell_scripts() -> list[Path]:
    return sorted(p for p in SCRIPTS.glob("*.sh")) if SCRIPTS.is_dir() else []


def _python_scripts() -> list[Path]:
    return sorted(p for p in SCRIPTS.glob("*.py")) if SCRIPTS.is_dir() else []


def test_the_lane_ships_the_scripts_it_documents():
    actual = {p.name for p in _shell_scripts()} | {p.name for p in _python_scripts()}
    assert EXPECTED <= actual, f"missing shipped scripts: {sorted(EXPECTED - actual)}"


def test_every_shell_script_is_executable():
    # A non-executable gate script cannot be run the way the SKILL.md tells a reader to run it.
    scripts = _shell_scripts()
    assert scripts, "no shell scripts found; the glob is wrong"
    bad = [p.name for p in scripts if not os.access(p, os.X_OK)]
    assert not bad, f"not executable: {bad}"


def test_every_shell_script_parses():
    for p in _shell_scripts():
        r = subprocess.run(["bash", "-n", str(p)], capture_output=True, text=True)
        assert r.returncode == 0, f"{p.name} has a syntax error:\n{r.stderr}"


def test_every_python_script_parses():
    for p in _python_scripts():
        try:
            ast.parse(p.read_text())
        except SyntaxError as exc:
            raise AssertionError(f"{p.name} does not parse: {exc}") from exc


def test_a_gate_script_is_not_left_empty():
    # An empty file parses and is executable, so the two checks above would both pass.
    for p in _shell_scripts() + _python_scripts():
        body = [ln for ln in p.read_text().splitlines() if ln.strip()]
        assert len(body) > 5, f"{p.name} is effectively empty ({len(body)} non-blank lines)"


def test_the_audit_tools_count_deletion_the_same_way():
    """Two audits of one repository must not disagree, or one of them is lying to the owner.

    `salvage-audit.sh` and `salvage-four-bucket.py` answer the same question -- "what is safe to
    delete, what must be preserved" -- so a divergence means a prune decision taken on the wrong
    number. This asserts the *rules*, not a snapshot of the counts (the repository changes every
    minute, and an exact-count test would red on every unrelated push).

    Measured divergence that motivated this: the python tool first reported
    `safe to delete: 45 branches / 132 worktrees` against the shell's `162 / 125`, because it
    (a) counted `total - dirty` worktrees, marking CLEAN worktrees on unique branches as safe,
    and (b) excluded lossless orphans from the deletable branch count.
    """
    sh = (SCRIPTS / "salvage-audit.sh").read_text()
    py = (SCRIPTS / "salvage-four-bucket.py").read_text()

    # Each tool must derive its preserve set as a UNION of dirty and unique-branch worktrees.
    # A plain `total - dirty` subtraction is the bug; it is not allowed to reappear.
    assert "len(keep)" in py, "python tool must subtract the union, not just dirty"
    assert "len(wts)-len(dirty_all)" not in py, "python tool regressed to total-minus-dirty"
    assert "set(wt_uniq)" in sh, "shell tool must union its unique-branch worktrees"

    # And the deletable-branch count must be "everything except the unique set", never a
    # bucket enumeration that silently drops lossless orphans.
    assert "len(rows) - len(unique_orphans)" in py, \
        "deletable branches must be total-minus-unique, not a bucket sum"
    assert "for r in rows if r['bucket'] in ('merged-and-clean', 'unmerged-with-a-PR')" not in py, \
        "deletable branches regressed to a bucket enumeration that drops lossless orphans"
