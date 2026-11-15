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

