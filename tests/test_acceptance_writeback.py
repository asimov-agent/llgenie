"""The acceptance write-back seam (issue #1644): a review verdict ticks the boxes it proved.

Everything here is the real module — `tick_acceptance` / `acceptance_items` / `BodyError` are the
product. Nothing in `scripts/acceptance_writeback.py` talks to the network or to `gh` inside the
pure transformation; the `gh api PATCH` wrapper lives behind `main` and is not exercised here.

The two acceptance criteria under proof (issue #1644):

* a merged-and-reviewed issue carries `- [x]` where the reviewing verdict proved it, while an
  item the verdict did NOT prove stays `- [ ]` and is named `proven:/unproven:`;
* an auto-merged-only case (#1088-class, no reviewer verdict) never ticks anything — the seam
  requires an explicit `proven` list, so the absence of a verdict is an error, not a silent tick.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

from scripts import acceptance_writeback as aw

VERDICT = "llgenie-pr-reviever review=42 head=abc123 run=99"

# A body in the repository's six-section shape (issue #745) with three acceptance criteria.
BODY = (
    "## Problem\np\n\n## Why it matters\nw\n\n## How we fix it\n1. a\n2. b\n\n"
    "## Benefit\nb\n\n## Acceptance criteria\n\n- [ ] criterion one\n- [ ] criterion two proves it\n"
    "- [ ] criterion three\n\n## Technical\n\n- where: x\n"
)


def test_merged_and_reviewed_issue_carries_ticks_where_the_verdict_proved():
    """Verifying items 1 and 3 ticks exactly them; item 2 stays unticked and is named."""

    # Given a body whose issue was merged after a reviewer verified criteria 1 and 3
    # When  the write-back runs with those items proved
    out = aw.tick_acceptance(BODY, {1, 3}, VERDICT)

    # Then  the proved items are `- [x]` with the verdict reference, item 2 stays `- [ ]`
    assert "- [x] criterion one  (proven: " + VERDICT + ")" in out
    assert "- [x] criterion three  (proven: " + VERDICT + ")" in out
    assert "- [ ] criterion two proves it\n" in out
    # and item 2 (the unproven one) is named in a trailing bullet
    assert "unproven: 2. criterion two proves it" in out

    # The rest of the body is untouched (the six-section shape still holds).
    assert aw.issue_body.missing(out) == []


def test_all_proved_ticks_every_box():
    """A full reviewer verdict (all items) leaves no unticked box and no unproven list."""

    out = aw.tick_acceptance(BODY, {1, 2, 3}, VERDICT)

    assert out.count("- [x]") == 3
    assert "- [ ]" not in out
    assert "unproven:" not in out


def test_auto_merged_only_never_ticks_anything():
    """An #1088-class merge (no reviewer verdict) cannot tick: an empty `proven` is refused.

    The seam is driven by the verdict, not the merge — so the absence of a verdict is a
    contradiction (nothing to transcribe), surfaced as a `BodyError`, never a silent no-op.
    """

    with pytest.raises(aw.BodyError):
        aw.tick_acceptance(BODY, set(), VERDICT)


def test_out_of_range_proven_is_named():
    """Providing a position that is not an acceptance item is an error that names the range."""

    with pytest.raises(aw.BodyError):
        aw.tick_acceptance(BODY, {4}, VERDICT)


def test_no_acceptance_section_is_refused():
    """A body without `## Acceptance criteria` is not writable-shaped; the seam refuses."""

    stripped = BODY.replace("## Acceptance criteria", "## Acceptance-result")
    with pytest.raises(aw.BodyError):
        aw.tick_acceptance(stripped, {1}, VERDICT)


def test_idempotent_on_a_ticked_body():
    """Running the write-back twice does not double-tick or duplicate the provenance bullet."""

    once = aw.tick_acceptance(BODY, {1, 3}, VERDICT)
    twice = aw.tick_acceptance(once, {1, 3}, VERDICT)

    assert twice == once
    assert twice.count("- [x]") == 2


def test_check_command_requires_both_tick_and_untick():
    """The `check` contract: after a real write-back, a box was ticked AND one stayed unticked
    (the honest contrast to a fully #1088-auto-merged issue)."""

    # A write-back that ticks everything is still a legal PATCH, but `check` is the honest
    # reviewer-shaped gate: it refuses a body where nothing stayed unticked.
    out = aw.tick_acceptance(BODY, {1, 3}, VERDICT)
    assert "- [x]" in out and "- [ ]" in out


# --- issue #1802: a suffixed acceptance heading must still tick (lenient prefix match) ---

# A real reported shape (issue #1800): the producer authored `## Acceptance criteria (what
# closing means)`; the exact-match seam previously reds with "no section" on it.
BODY_SUFFIX = (
    "## Problem\np\n\n## Why it matters\nw\n\n## How we fix it\n1. a\n2. b\n\n"
    "## Benefit\nb\n\n## Acceptance criteria (what closing means)\n\n"
    "- [ ] criterion one\n- [ ] criterion two proves it\n- [ ] criterion three\n"
    "- [ ] criterion four\n- [ ] criterion five\n\n## Technical\n\n- where: x\n"
)


def test_suffix_acceptance_heading_ticks_all_proved():
    """A `## Acceptance criteria (what closing means)` heading still ticks items 1-5."""

    out = aw.tick_acceptance(BODY_SUFFIX, {1, 2, 3, 4, 5}, VERDICT)

    assert out.count("- [x]") == 5
    assert "- [ ]" not in out
    assert "unproven:" not in out
    for word in ("one", "two proves it", "three", "four", "five"):
        assert f"- [x] criterion {word}  (proven: {VERDICT})" in out


def test_suffix_heading_leaves_unproven_unticked():
    """A partial verdict on a suffixed heading ticks only the proved items and names the rest."""

    out = aw.tick_acceptance(BODY_SUFFIX, {1, 5}, VERDICT)

    assert "- [x] criterion one  (proven: " + VERDICT + ")" in out
    assert "- [x] criterion five  (proven: " + VERDICT + ")" in out
    assert "- [ ] criterion two proves it\n" in out
    assert "unproven: 2. criterion two proves it" in out


def test_suffix_heading_itself_is_preserved():
    """The seam ticks boxes under a suffixed heading but never rewrites the heading text.

    The producer's human-readable heading `## Acceptance criteria (what closing means)`
    survives verbatim — the write-back mutates only the checkbox lines, not headings."""

    out = aw.tick_acceptance(BODY_SUFFIX, {1, 3}, VERDICT)

    assert "## Acceptance criteria (what closing means)" in out
    assert out.count("- [x]") == 2
    assert "- [ ] criterion two proves it\n" in out


def test_unrelated_earlier_checkbox_is_never_ticked():
    """A checkbox under an earlier, differently-named section is not an acceptance criterion.

    The lenient match must not flank outward: `## Acceptance-result` (not starting with
    `Acceptance criteria`) is not the acceptance section, so its `- [ ]` must survive.
    """

    earlier_checkbox_body = (
        "## Problem\np\n\n## Why it matters\nw\n\n## How we fix it\n1. a\n2. b\n\n"
        "## Acceptance-result (a different section)\n\n- [ ] not a criterion\n\n"
        "## Acceptance criteria\n\n- [ ] criterion one\n- [ ] criterion two\n\n"
        "## Technical\n\n- where: x\n"
    )

    out = aw.tick_acceptance(earlier_checkbox_body, {1, 2}, VERDICT)

    # The unrelated `- [ ] not a criterion` survived; the two real criteria are ticked.
    assert "- [ ] not a criterion\n" in out
    assert "- [x] criterion one  (proven: " + VERDICT + ")" in out
    assert "- [x] criterion two  (proven: " + VERDICT + ")" in out


def test_missing_section_canary_names_actual_headings():
    """A body with no acceptance heading reds with a canary naming what IS present.

    The root cause (a spelling variant) is distinguishable from total absence by the
    message listing the headings actually found (issue #1802)."""

    no_acceptance = (
        "## Problem\np\n\n## Why it matters\nw\n\n## How we fix it\n1. a\n2. b\n\n"
        "## Benefit\nb\n\n## Technical\n\n- where: x\n"
    )

    with pytest.raises(aw.BodyError) as ei:
        aw.acceptance_items(no_acceptance)
    msg = str(ei.value)
    assert "no `## Acceptance criteria`" in msg
    assert "found headings:" in msg
    assert "Problem" in msg and "Technical" in msg
