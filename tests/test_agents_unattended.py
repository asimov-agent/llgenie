#!/usr/bin/env python3
"""Every unattended agent leg must forbid questions, and exit 3 must be named (issues #543, #577).

`hermes -z … --yolo` auto-approves SHELL COMMANDS; `--accept-hooks` auto-approves HOOKS. Neither answers the
agent's own `clarify` tool: in a detached run Hermes prints "Input required; detached without cancelling" and
exits 3, the tree is unchanged, and the leg reports "changed nothing" — a misleading diagnosis (measured in the
sibling repo's issue-bot, run 39905705714).

The contract now lives once, in the project skill `bot-unattended`, and every leg preloads it with `-s`
(issue #577). These tests read the real files: every `hermes -z` leg preloads the skill, the skill carries the
rule, and the issue-bot's failure step names rc=3 for what it is.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import check_agent_skills as cas  # noqa: E402

SHARED = (REPO / ".hermes" / "skills" / "bot-unattended" / "SKILL.md").read_text()
WORKFLOW = (REPO / ".github" / "workflows" / "issue-bot.yml").read_text()


def test_every_unattended_leg_preloads_the_shared_skill():
    """A leg's prompt no longer carries the paragraph: the preloaded skill does."""

    # Given every `hermes -z` leg in the tree
    found_legs = cas.legs(REPO)

    # When  its preloaded skills are read
    # Then  each one preloads bot-unattended, and the rule is not pasted back into a recipe
    assert len(found_legs) >= 7, "the Makefile's agent legs disappeared"
    for leg in found_legs:
        assert cas.SHARED_SKILL in leg.skills, f"{leg.where} must preload {cas.SHARED_SKILL}"
        assert "NEVER ask a question" not in leg.prompt, f"{leg.where} duplicates the contract"


def test_the_shared_skill_forbids_asking_and_names_the_failure_mode():
    """The one file must say what a question does, not just that questions are discouraged."""

    # Given the bot-unattended skill
    # When  its contract is read
    # Then  it forbids asking, names the clarify/exit-3 failure, and says a question fails the run
    assert "Never ask a question and never wait for input" in SHARED
    assert "clarify" in SHARED and "exit 3" in SHARED
    assert "A question fails the run" in SHARED
    assert "REFINED" in SHARED and "EVIDENCE" in SHARED, "the open-decision path is named"


def test_exit_three_is_named_as_asked_for_input_not_changed_nothing():
    """The failure step must not report a question as 'changed nothing'."""

    # Given the issue-bot workflow
    # When  the failure step's body is read
    # Then  rc=3 has its own message, before the generic one
    asked = WORKFLOW.index("the agent asked for input")
    generic = WORKFLOW.index("issue-bot changed nothing")
    assert asked < generic, "the rc=3 branch must come first"
    assert 'steps.impl.outputs.rc }}" = "3"' in WORKFLOW
