#!/usr/bin/env python3
"""Every unattended agent leg must forbid questions, and exit 3 must be named (issues #543, #577).

`hermes -z … --yolo` auto-approves SHELL COMMANDS; `--accept-hooks` auto-approves HOOKS. Neither answers the
agent's own `clarify` tool: in a detached run Hermes prints "Input required; detached without cancelling" and
exits 3, the tree is unchanged, and the leg reports "changed nothing" — a misleading diagnosis (measured in the
sibling repo's issue-bot, run 39905705714).

The rule used to be pasted into all seven prompts. It is now stated ONCE, in the
`.hermes/skills/bot-unattended/SKILL.md` skill every leg preloads (issue #577), so these tests read the real
files: the skill carries the rule, every leg preloads it, no leg inlines it again, and the issue-bot's failure
step still names rc=3 for what it is.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

from scripts import check_agent_skills as guard

MAKEFILE = (REPO / "Makefile").read_text()
CONTRACT = (REPO / ".hermes" / "skills" / "bot-unattended" / "SKILL.md").read_text()
WORKFLOW = (REPO / ".github" / "workflows" / "issue-bot.yml").read_text()


def test_the_unattended_contract_states_the_rule_and_the_failure_mode():
    """The skill every leg preloads carries the rule, its exit code and why."""

    # Given the shared unattended skill
    # When  its contract is read
    # Then  it forbids asking, names `clarify`/exit 3, and says what to do instead
    assert "## Rules" in CONTRACT
    assert "Never ask a question" in CONTRACT
    assert "clarify" in CONTRACT and "exits 3" in CONTRACT
    assert "detached" in CONTRACT


def test_every_leg_preloads_the_unattended_contract_and_none_inlines_it():
    """The rule lives in one file and is loaded, never copied into a recipe."""

    # Given every agent leg in the tree
    legs = guard.iter_legs(REPO)

    # When  each leg's preload list and prompt are read
    # Then  every leg preloads the contract, and no prompt repeats it
    assert len(legs) >= 8, f"only {len(legs)} leg(s) found: the scan reads nothing"
    for leg in legs:
        assert guard.UNATTENDED_SKILL in leg["skills"], leg["where"]
        assert guard.INLINE_UNATTENDED not in leg["prompt"], leg["where"]
        assert "a question fails the run" not in leg["prompt"], leg["where"]


def test_the_former_inline_copy_is_gone_from_the_makefile():
    """The paragraph that was duplicated seven times is not in the recipes any more."""

    # Given the Makefile
    # When  it is searched for the old inline paragraph
    # Then  it is absent — the skill is the only place it lives
    assert "UNATTENDED: this run has no user" not in MAKEFILE
    assert "a question fails the run" not in MAKEFILE


def test_exit_three_is_named_as_asked_for_input_not_changed_nothing():
    """The failure step must not report a question as 'changed nothing'."""

    # Given the issue-bot workflow
    # When  the failure step's body is read
    # Then  rc=3 has its own message, before the generic one
    asked = WORKFLOW.index("the agent asked for input")
    generic = WORKFLOW.index("issue-bot changed nothing")
    assert asked < generic, "the rc=3 branch must come first"
    assert 'steps.impl.outputs.rc }}" = "3"' in WORKFLOW
