"""A manual `issue-bot` dispatch with no issue number picks one issue itself (issue #472).

The bot was born for this: `scripts/issue_implementer.py::dispatch()` takes `force_issue: int | None`,
and with `None` it applies the 3/day cap, picks the oldest `agent:implement` issue (then the oldest
`agent:ready`), claims it, and writes `issue.md` + a branch for the verdict leg to route
(implement / refine / close). The daily schedule uses exactly that path.

What made it unreachable was the dispatch FORM: `issue_number` was `required: true`, so GitHub refused
the dispatch before a run existed —

```
$ gh workflow run issue-bot.yml --repo asimov-agent/llgenie
could not create workflow dispatch event: HTTP 422: Required input 'issue_number' not provided
```

These cases pin the contract at both ends: the form does not require a number, an empty form really
reaches `force_issue=None` (through the workflow expression AND the Makefile's `$(if …)` expansion),
a supplied number still pins that issue, and the header + README say the same thing the code does.
Every case reads the real files and expands the real recipe (`make -n`), so no copy of the workflow is
tested instead of the workflow.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github" / "workflows" / "issue-bot.yml"
MAKEFILE = REPO / "Makefile"
README = REPO / "README.md"
#: The dispatch table lives in docs/BOTS.md — the README is the user guide (issue #678).
BOTS = REPO / "docs" / "BOTS.md"

from scripts import issue_implementer


def _issue_number_block() -> str:
    """The `issue_number:` input block, up to the next line at the same indentation."""
    text = WORKFLOW.read_text()
    start = text.index("      issue_number:")
    rest = text[start:]
    lines = rest.splitlines()
    block = [lines[0]]
    for line in lines[1:]:
        if line.strip() and not line.startswith("        "):
            break
        block.append(line)
    return "\n".join(block)


def _dispatch_recipe(force_issue: str) -> str:
    """What `make issue-bot-dispatch` would run, for a given FORCE_ISSUE (`make -n` runs nothing)."""
    return subprocess.run(
        ["make", "-n", "issue-bot-dispatch", f"FORCE_ISSUE={force_issue}", "REPO=asimov-agent/llgenie"],
        cwd=REPO, capture_output=True, text=True, check=False,
    ).stdout


def test_the_dispatch_form_does_not_require_an_issue_number():
    """The form must accept a blank issue number, and say what blank does."""

    # Given the workflow's issue_number input block
    block = _issue_number_block()

    # When  its required flag, default and description are read
    required = re.search(r"^\s+required:\s*(\S+)\s*$", block, re.M)
    default = re.search(r'^\s+default:\s*"([^"]*)"\s*$', block, re.M)

    # Then  it is optional, defaults empty, and the description promises the bot picks
    assert required is not None, block
    assert required.group(1) == "false", f"issue_number must not be required, got {required.group(1)}"
    assert default is not None and default.group(1) == "", block
    assert "BLANK" in block, "the description must say what a blank value does"
    assert "agent:implement" in block, "the description must name the label the bot picks from"
    assert "picks" in block


def test_a_blank_dispatch_reaches_the_picking_path():
    """An empty form value must land on `force_issue=None`, not on a flag with an empty argument."""

    # Given the workflow's dispatch step and the dispatcher's signature
    workflow = WORKFLOW.read_text()
    signature = issue_implementer.dispatch.__defaults__ or ()

    # When  the FORCE_ISSUE expression and the recipe expansion for an empty value are read
    expression = re.search(r"FORCE_ISSUE:\s*(.+)$", workflow, re.M)
    recipe = _dispatch_recipe("")

    # Then  the step falls back to empty, the recipe passes no --force-issue, and the default is None
    assert expression is not None, "the dispatch step must derive FORCE_ISSUE"
    assert "inputs.issue_number" in expression.group(1), expression.group(1)
    assert expression.group(1).rstrip().endswith("}}"), expression.group(1)
    assert "|| ''" in expression.group(1), expression.group(1)
    assert "--force-issue" not in recipe, recipe
    assert None in signature, f"dispatch() must default force_issue to None, got {signature}"


def test_a_supplied_number_still_pins_that_issue():
    """A number in the form must still pin exactly that issue."""

    # Given the same recipe
    # When  FORCE_ISSUE carries a number
    recipe = _dispatch_recipe("1234")

    # Then  the flag is passed with that number
    assert "--force-issue 1234" in recipe, recipe


def test_the_header_and_the_dispatch_table_state_the_same_contract():
    """The file header and the dispatch table must say what the code does, and the guard must pass."""

    # Given the workflow header, the dispatch table and the dispatch-forms guard
    header = WORKFLOW.read_text().split("\non:", 1)[0]
    readme = BOTS.read_text()

    # When  the blank-means-pick wording and the guard's verdict are read
    table_row = [line for line in readme.splitlines() if "`issue-bot.yml`" in line]
    guard = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "check_dispatch_forms.py"), "check"],
        cwd=REPO, capture_output=True, text=True, check=False,
    )

    # Then  both documents carry it and the guard is green
    assert "OPTIONAL" in header and "picks" in header, header[-600:]
    assert table_row, "the docs/BOTS.md dispatch table must describe issue-bot.yml"
    assert any("optional" in row and "BLANK" in row for row in table_row), table_row
    assert guard.returncode == 0, guard.stdout + guard.stderr
