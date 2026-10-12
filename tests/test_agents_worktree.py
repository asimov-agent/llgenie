"""Each agent works in its own git worktree (issue #216)."""
from __future__ import annotations

from pathlib import Path

AGENTS = Path(__file__).resolve().parent.parent / "AGENTS.md"


def test_each_agent_works_in_its_own_worktree():
    """The rulebook sends every agent to its own worktree."""

    # Given the agent rulebook
    text = AGENTS.read_text()

    # When the git workflow section is read
    start = text.index("## Git workflow")
    section = text[start:text.index("## PR review comments")]

    # Then each agent must use its own worktree and must not edit the user's checkout
    assert "Each agent works in its own git worktree, every time" in section
    assert "git worktree add -b feat/<kebab> ../llgenie-wt/<kebab> origin/main" in section
    assert "Never edit" in section
    assert "NO git worktrees" not in text
