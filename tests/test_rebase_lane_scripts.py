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


def _load_audit_module():
    """Import the shipped audit tool as a module so its verdict function can be unit-tested.

    Testing `summarise` directly rather than shelling out to both tools: the tools need `gh` and
    a real repository, which CI does not have, and AGENTS.md forbids skipped tests. The counting
    RULES are what went wrong twice, and they are pure.
    """
    import importlib.util

    path = SCRIPTS / "salvage-four-bucket.py"
    spec = importlib.util.spec_from_file_location("salvage_four_bucket", path)
    assert spec and spec.loader, f"cannot load {path}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_a_clean_worktree_on_a_unique_branch_is_preserved():
    """The first real bug: `total - dirty` marked clean work on unique branches as deletable."""
    mod = _load_audit_module()
    rows = [{"branch": "uniq", "tip": "aaaa1111", "bucket": "orphan",
             "added": ["only/here.md"], "held_by_pr": None}]
    # clean (dirty=0) and its HEAD is the unique tip — deleting it loses the only copy
    wts = [{"path": "/wt/uniq", "branch": "uniq", "head": "aaaa1111", "dirty": 0}]

    verdict = mod.summarise(rows, wts)
    assert verdict["safe_worktrees"] == 0, "a clean worktree on a unique branch was called safe"
    assert [w["path"] for w in verdict["keep"]] == ["/wt/uniq"]


def test_lossless_orphans_are_deletable_not_preserved():
    """The second real bug: a bucket enumeration dropped lossless orphans (45 vs 162)."""
    mod = _load_audit_module()
    rows = [
        {"branch": "merged", "tip": "b1", "bucket": "merged-and-clean"},
        {"branch": "onpr", "tip": "b2", "bucket": "unmerged-with-a-PR"},
        {"branch": "lossless", "tip": "b3", "bucket": "orphan", "added": [], "held_by_pr": None},
        {"branch": "held", "tip": "b4", "bucket": "orphan",
         "added": ["x.md"], "held_by_pr": 42},
        {"branch": "uniq", "tip": "b5", "bucket": "orphan",
         "added": ["y.md"], "held_by_pr": None},
    ]

    verdict = mod.summarise(rows, [])
    assert verdict["safe_branches"] == 4, "lossless/held-by-PR orphans must count as deletable"
    assert [r["branch"] for r in verdict["unique_orphans"]] == ["uniq"]


def test_dirty_and_unique_are_union_not_sum():
    """Preserved worktrees must be a UNION: a path that is both counts once."""
    mod = _load_audit_module()
    rows = [{"branch": "uniq", "tip": "c1", "bucket": "orphan",
             "added": ["z.md"], "held_by_pr": None}]
    wts = [{"path": "/wt/both", "branch": "uniq", "head": "c1", "dirty": 3}]

    verdict = mod.summarise(rows, wts)
    assert len(verdict["keep"]) == 1, "a dirty unique worktree must be counted once, not twice"
    assert verdict["safe_worktrees"] == 0


def test_the_shipped_tools_exist_and_are_independent_implementations():
    """Two audits of one question must stay separate programs, or the cross-check is meaningless.

    Running both needs `gh` and a live repository, so this asserts only what is testable here:
    both are shipped, and neither silently delegates to the other (which would make their
    agreement vacuous).
    """
    sh = (SCRIPTS / "salvage-audit.sh").read_text()
    py = (SCRIPTS / "salvage-four-bucket.py").read_text()
    assert "salvage-four-bucket" not in sh, "shell audit delegates to the python one"
    assert "salvage-audit.sh" not in py.replace("# ", ""), "python audit delegates to the shell"
    assert "MUST BE PRESERVED" in sh and "must be preserved" in py, \
        "both must report the same two conclusion lines for a reader to compare"
