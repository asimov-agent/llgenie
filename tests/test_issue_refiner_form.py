"""Issue #1805: the refine path must not silently accept a hand-authored issue body that lacks
the acceptance-criteria form (gap under #1796 #3). `render()` — the agent's input file the `/ refine`
endpoint produces — calls `issue_body.missing()` on the source body and, when it finds shape defects,
emits a FINDING so the review agent restates with tickable `- [ ]` criteria (never restating the
reader itself, never editing the human's body). A body that already conforms is left byte-identical.

The tests use a body that passes the shape (the refiner never fabricates criteria) and one genuine
hand-authored body that lacks the form, mirroring the real world the refiner operates on.
"""

from __future__ import annotations

from pathlib import Path

from scripts import issue_refiner as ir


def _conforming_body() -> str:
    """A producer-rendered body: every required section, `## Acceptance criteria` with a `- [ ]`."""
    return (
        "## Problem\nbroken\n"
        "## Why it matters\nmatters\n"
        "## How we fix it\n1. fix it\n"
        "## Benefit\nworks\n"
        "## Acceptance criteria\n- [ ] it works again\n"
        "## Technical\n- scripts/foo.py\n"
    )


def _hand_authored_without_form() -> str:
    """A genuine hand-authored issue: prose plus a `## Acceptance criteria` heading with NO checkbox
    — the exact #1805 shape that slips through today because `render()` never calls `missing()`."""
    return (
        "## Problem\nIt is slow.\n"
        "## Why it matters\nSlow costs time.\n"
        "## How we fix it\n1. Make it faster.\n"
        "## Benefit\nIt is fast.\n"
        "## Acceptance criteria\nIt is fast enough.\n"   # no `- [ ]` item
        "## Technical\n- scripts/foo.py\n"
    )


def _detail(body: str) -> dict:
    return {"number": 5, "title": "t", "state": "open", "author": {"login": "a"},
            "labels": [], "body": body}


def test_render_leaves_a_conforming_body_byte_identical():
    """#1805 criterion 4: a producer-rendered (already-conforming) issue passes through unchanged —
    no flag is emitted, so `render()` output for a conforming body must not mention the form."""
    out = ir.render(_detail(_conforming_body()), [])
    assert "Acceptance-criteria form" not in out
    assert "## Issue body\n\n" in out
    assert "## Comments (oldest first, 0)" in out


def test_render_flags_a_hand_authored_body_without_a_tickable_form():
    """#1805 criterion 1+2: a hand-authored body that lacks a tickable `## Acceptance criteria`
    round-trips through `/ refine` and lands on the endpoint (the agent input) WITH the finding."""
    out = ir.render(_detail(_hand_authored_without_form()), [])
    assert "## Acceptance-criteria form (issue #1796 #3)" in out
    assert "`issue_body.missing()`" in out
    assert "- `## Acceptance criteria` carries no `- [ ]` item" in out
    # the flag tells the agent to restate with checkboxes — emission, never silent acceptance
    assert "- [ ]" not in out.split("## Acceptance-criteria form")[0], \
        "the finding must not fabricate criteria that are not in the source"


def test_the_flag_emits_every_missing_section_as_a_finding():
    """#1805 criterion 1: `issue_body.missing()` names each shape defect; the flag surfaces them
    (reusing the reader verbatim), so the agent knows exactly which sections the form needs."""
    body = "## Problem\np\n"   # only one section — four required ones missing
    flag = ir.acceptance_form_flag(body)
    assert "## Why it matters` is missing" in flag
    assert "## How we fix it` is missing" in flag
    assert "## Benefit` is missing" in flag
    assert "## Acceptance criteria` is missing" in flag


def test_no_flag_for_a_conforming_body_but_a_flag_for_an_empty_one():
    """#1805 criterion 4: `missing()==[]` means nothing to emit; an empty body (all sections
    missing) is exactly the hand-authored shape the refine path must not silently accept."""
    assert ir.acceptance_form_flag(_conforming_body()) == ""
    assert "## Problem` is missing" in ir.acceptance_form_flag("")
