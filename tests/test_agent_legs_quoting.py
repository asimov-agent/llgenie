"""Every agent leg's expanded command must be shell-safe (issue #641).

GNU make splits `$(call …)` arguments on commas in the UNEXPANDED text, so a literal `-s a,b` inside
`$(call scrubbed_run,…)` keeps only `-s a`. The rest of the command is dropped, the shell sees an
unclosed single quote and the leg dies with `unexpected EOF while looking for matching '` before the
agent ever runs — measured on rebase-bot, which left every conflicted PR DIRTY (#602, #605).

The check is the expanded recipe itself (`make -n <target>`), not the Makefile text: what matters is
the command the shell would receive.
"""

from __future__ import annotations

import re
import subprocess

from pathlib import Path
from conftest import makefiles_text  # noqa: E402  (the include-resolving Makefile reader)

REPO = Path(__file__).resolve().parents[1]


def _legs() -> list[str]:
    """Every target whose recipe goes through `$(call scrubbed_run,…)`."""
    targets, current = [], ""
    for line in makefiles_text().splitlines():
        m = re.match(r"^([A-Za-z0-9_.%-]+):", line)
        if m:
            current = m.group(1)
        if "$(call scrubbed_run" in line and current:
            targets.append(current)
    return targets


def _expanded(target: str) -> str:
    r = subprocess.run(["make", "-n", target], cwd=REPO, capture_output=True, text=True)
    return r.stdout + r.stderr


def test_every_scrubbed_leg_expands_to_balanced_quotes():
    """An odd number of single quotes means the command was cut and the agent never starts."""

    # Given every public agent leg (the ones wrapped by scrubbed_run)
    legs = _legs()

    # When  make expands each one, and its expanded command is read
    bad = {}
    for target in legs:
        text = _expanded(target)
        quotes = text.count("'")
        if quotes % 2:
            bad[target] = quotes

    # Then  every expanded command has balanced quotes
    assert legs, "no scrubbed_run legs found"
    assert bad == {}, f"odd number of single quotes (truncated command) in: {bad}"


def test_rebase_bot_keeps_both_of_its_skills():
    """The leg that inlines its hermes command must still carry `-s rebase-conflict,bot-unattended`."""

    # Given the rebase-bot agent leg (the one that cannot use a `_<leg>` target, issue #460)
    text = _expanded("rebase-bot-agent")

    # When  its expanded command is read
    skills = re.search(r"-s ([a-z0-9,-]+)", text)

    # Then  the comma-separated list survived the $(call) expansion
    assert skills, text[-400:]
    assert skills.group(1) == "rebase-conflict,bot-unattended", skills.group(1)


def test_the_skills_come_from_a_variable_not_a_literal_comma():
    """A literal comma inside the call is the defect; the variable is the fix."""

    # Given the rebase-bot recipe in the Makefile
    text = makefiles_text()
    recipe = text.split("\nrebase-bot-agent:", 1)[1].split("\n# Hermes runs directly", 1)[0]

    # When  the leg's scrubbed_run call is read
    # Then  it references the skills variable and contains no literal `-s a,b`
    assert "$(REBASE_BOT_SKILLS)" in recipe
    assert "rebase-conflict,bot-unattended" not in recipe
    assert "REBASE_BOT_SKILLS := rebase-conflict,bot-unattended" in text
