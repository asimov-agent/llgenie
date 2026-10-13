"""Every change surfaces gaps -> issues, never implementation (issue #231)."""
from __future__ import annotations

from pathlib import Path

AGENTS = Path(__file__).resolve().parent.parent / "AGENTS.md"
MARKER = "## Analysis: every change surfaces gaps"


def test_agents_md_requires_analysis_into_issues():
    """The rulebook makes analysis an issue-producing activity, not code."""

    # Given the agent rulebook
    text = AGENTS.read_text()

    # When the analysis rule is read
    assert MARKER in text, "AGENTS.md lost the 'analysis surfaces gaps' rule"
    section = text[text.index(MARKER):]
    section = section[:section.index("\n## ", 1)]

    # Then it mandates analysis into separate issues, never an implementation
    assert "real gaps and technical debt" in section
    assert "ships issues, not code" in section
    assert "Separate the issues" in section
    assert "Never implement from this analysis" in section
