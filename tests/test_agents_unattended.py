#!/usr/bin/env python3
"""Every unattended agent leg must forbid questions, and exit 3 must be named (issue #543).

`hermes -z … --yolo` auto-approves SHELL COMMANDS; `--accept-hooks` auto-approves HOOKS. Neither answers the
agent's own `clarify` tool: in a detached run Hermes prints "Input required; detached without cancelling" and
exits 3, the tree is unchanged, and the leg reports "changed nothing" — a misleading diagnosis (measured in the
sibling repo's issue-bot, run 39905705714).

The contract is textual, so these tests read the real files: each prompt carries the rule, the fix-bot's rules
file carries it, and the issue-bot's failure step names rc=3 for what it is.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MAKEFILE = (REPO / "Makefile").read_text()
RULES = (REPO / "scripts" / "fix_bot_rules.md").read_text()
WORKFLOW = (REPO / ".github" / "workflows" / "issue-bot.yml").read_text()

#: The prompts that run inside the agent image with no user attached.
PROMPTS = ("_issue-bot-triage", "_implement-issue", "_issue-refiner", "_architecture-bot-doc",
           "_agent-fetch")


def test_every_unattended_prompt_forbids_asking_a_question():
    """A question in a detached leg is a failed run, so the prompt has to say so."""

    # Given the Makefile's agent prompts
    # When  each prompt body is read (the recipe line that starts with `hermes -z "`)
    # Then  every one carries the UNATTENDED rule
    assert MAKEFILE.count("UNATTENDED: this run has no user") == 5, (
        "expected the rule on all five hermes prompts (triage, implement, refine, architecture, fetch)")
    for name in PROMPTS:
        assert name in MAKEFILE, name

    # And the rule says what to do instead of asking
    assert "NEVER ask a question" in MAKEFILE
    assert "a question fails the run" in MAKEFILE


def test_the_fix_bot_rules_forbid_asking_too():
    """The repair loop has the same failure mode, and the same rule."""

    # Given the fix-bot's rules file
    # When  its contract is read
    # Then  it states that the run is unattended and that a clarify detaches it
    assert "## You are unattended" in RULES
    assert "clarify" in RULES and "exits 3" in RULES


def test_exit_three_is_named_as_asked_for_input_not_changed_nothing():
    """The failure step must not report a question as 'changed nothing'."""

    # Given the issue-bot workflow
    # When  the failure step's body is read
    # Then  rc=3 has its own message, before the generic one
    asked = WORKFLOW.index("the agent asked for input")
    generic = WORKFLOW.index("issue-bot changed nothing")
    assert asked < generic, "the rc=3 branch must come first"
    assert 'steps.impl.outputs.rc }}" = "3"' in WORKFLOW
