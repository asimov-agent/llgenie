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
EXPECTED = {"post-rebase-verify.sh", "salvage-audit.sh"}


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
