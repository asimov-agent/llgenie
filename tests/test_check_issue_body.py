"""The issue-body gate: it refuses a second shape, a lost rule, and a body its own checker rejects.

The gate reads real files, so the tests give it a real tree: each case writes the producer / AGENTS.md
/ skill it is about into `tmp_path` and calls the real `check(root)` — no monkeypatching of the check
logic itself, only its input tree.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

from scripts import check_issue_body as gate
from scripts import issue_body


def _tree(tmp_path: Path) -> Path:
    """A minimal but REAL tree: every producer renders, AGENTS.md and both skills state the rule."""
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    for rel, _ in issue_body.PRODUCERS:
        name = Path(rel).name
        (root / "scripts" / name).write_text(
            "import issue_body\n\n\ndef render(*a, **k):\n    return issue_body.render(*a, **k)\n",
            encoding="utf-8")
    shutil.copy(REPO / "AGENTS.md", root / "AGENTS.md")
    for rel in gate.SKILLS:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / rel, target)
    return root


def test_the_real_tree_passes():
    """The repository as it stands satisfies the rule its own gate enforces."""

    # Given the real checkout
    # When  the gate checks it
    findings = gate.check(REPO)

    # Then  there is nothing to report
    assert findings == [], findings


def test_a_hand_built_body_fails_the_gate(tmp_path):
    """A producer that spells the sections itself is a second shape, which is the defect."""

    # Given a tree whose security producer builds its body by hand
    root = _tree(tmp_path)
    (root / "scripts" / "security_issues.py").write_text(
        "def body_for(f):\n"
        "    return \"\\n\".join([\"## Problem\", \"x\", \"## Technical\", \"y\"])\n",
        encoding="utf-8")

    # When  the gate checks it
    findings = gate.check(root)

    # Then  it names that file, for both the missing import and the hand-built heading
    named = [f for f in findings if "security_issues.py" in f]
    assert any("import" in f for f in named), named
    assert any("section of its own" in f for f in named), named


def test_a_lost_agents_section_fails(tmp_path):
    """Deleting the rule from AGENTS.md must be a red gate, not a silent edit."""

    # Given a tree whose AGENTS.md no longer carries the section
    root = _tree(tmp_path)
    (root / "AGENTS.md").write_text("# AGENTS.md\n\nno issue-body rule here\n", encoding="utf-8")

    # When  the gate checks it
    findings = gate.check(root)

    # Then  it names the missing section
    assert any("AGENTS.md" in f and gate.AGENTS_HEADING in f for f in findings), findings


def test_an_issue_skill_without_the_shape_fails(tmp_path):
    """The legs that restate a human-written issue must state the shape themselves."""

    # Given a tree whose refiner skill dropped `## Acceptance criteria`
    root = _tree(tmp_path)
    rel = ".hermes/skills/issue-refiner/SKILL.md"
    text = (root / rel).read_text(encoding="utf-8").replace("## Acceptance criteria", "## Done")
    (root / rel).write_text(text, encoding="utf-8")

    # When  the gate checks it
    findings = gate.check(root)

    # Then  it names the skill AND the section it lost
    assert any(rel in f and "Acceptance criteria" in f for f in findings), findings


def test_the_renderer_and_the_checker_agree():
    """The gate's self-test: the renderer's own output is what the checker accepts."""

    # Given the renderer's canonical body
    body = issue_body.render(
        problem="p", why="w", how=["h"], benefit="b", acceptance=["a"], technical=["t"])

    # When  its own checker reads it
    # Then  it conforms, otherwise the gate would be decoration
    assert issue_body.missing(body) == []
