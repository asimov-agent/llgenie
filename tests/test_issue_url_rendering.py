"""Every issue-to-issue pointer is rendered as a full URL; a bare `#<n>` survives only inside code.

The product here is `scripts/issue_body.py::link_issue_cites` / `pointer_findings` and the `## Not
covered` bullets `render` writes. The reason is measured, not stylistic: `scripts/check_pr_acceptance.py`
reads a bare `#<n>` in an umbrella issue's body as an OPEN rollout lane and holds the umbrella's own
`closes #<umbrella>` (issue #3053's PR was held by `(#3050)` while #3050 was OPEN and cited #3053 back).
A pointer spelled as a URL is not a lane candidate, so a deferral list stops holding its own close.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

from scripts import issue_body as ib

BASE = "https://github.com/asimov-agent/llgenie"

FIELDS = dict(
    problem="the bump wave opened 7 PRs and every one of them was red on the structural gates",
    why="auto-merge could land none of them, so the pinned images stayed a week behind",
    how=["compose the body through one seam", "name the shape of the reference that broke"],
    benefit="the bump lane's PRs pass the gates they were structurally failing",
    acceptance=["the bump lane's PR is green on `guard` and `scope`"],
    technical=["`scripts/engine_bump_pr_body.py`"],
)


def _body(**extra):
    return ib.render(**{**FIELDS, **extra})


def test_a_deferral_list_renders_its_pointers_as_full_issue_urls():
    """issue #3055: a `## Not covered` bullet that defers behaviour to another issue names that issue
    as a full URL, so a reader clicks it and the umbrella's close is not held by its own scope list.
    """

    # Given deferral pointers written the way producers write them (`(#669)`, bare `#3050`)
    # When  the body is rendered through the seam
    body = _body(not_covered=[
        "the live read of the next bump wave is its own issue (#3053)",
        "the engine-bump lane is tracked separately as #3050",
        "retro-fitting the older open issues is a follow-up (#746, #669)",
    ])

    # Then  every pointer in `## Not covered` is a full issue URL and no bare cite is left
    section = ib.section_body(body, "Not covered")
    assert f"{BASE}/issues/3053" in section, section
    assert f"{BASE}/issues/3050" in section, section
    assert f"{BASE}/issues/746" in section and f"{BASE}/issues/669" in section, section
    assert ib.pointer_findings(body) == [], section
    assert ib.missing(body) == [], section


def test_a_bare_cite_outside_the_deferral_list_is_left_alone():
    """issue #3055: `## Not covered` is the only section whose cites are pointers. A `#1234` in the
    problem statement or the technical section names a fact, not a lane, and stays exactly as written.
    """

    # Given a body whose Problem and Technical cite issues
    body = _body(problem="the gate in PR #1234 reddened although its issue #1235 was closed",
                 technical=[f"issue #{3055}", "measured on PR #3053 at `scripts/check_pr_acceptance.py`"])

    # Then  neither section gained a URL, and the deferral section is absent
    assert "PR #1234" in ib.section_body(body, "Problem")
    assert f"{BASE}/issues/1234" not in body, body
    assert "PR #3053" in ib.section_body(body, "Technical"), body
    assert "Not covered" not in ib.headings(body), ib.headings(body)


def test_an_already_linked_pointer_is_not_rewritten_twice():
    """issue #3055: a pointer that already carries its issue URL (a body spliced from a rendered one, a
    measured gate message quoted verbatim) is left readable instead of nesting a link in a link.
    """

    # Given a deferral bullet that already names the URL and repeats the number
    line = f"- the trend-refresh lane is tracked as {BASE}/issues/3056 (issue #3056)"

    # When  the pointer writer runs over it
    linked = ib.link_issue_cites(line)

    # Then  the number is linked once and the line is unchanged
    assert linked.count(f"{BASE}/issues/3056") == 1, linked
    assert f"({BASE}/issues/" not in linked, linked
    assert linked == line, linked


def test_a_cite_inside_code_or_a_fence_stays_bare():
    """issue #3055: quoted gate wording and code samples are evidence, not pointers — rewriting them
    would make the quoted message stop matching the message the gate actually prints.
    """

    # Given a pointer-shaped cite inside inline code and inside a fenced block
    text = (
        f"- the gate reads `Not covered: bare cites hold the close (#1234)`\n"
        "```\n"
        "- a fence bullet that names #1235\n"
        "```\n"
    )

    # When  the pointer writer runs over it
    out = ib.link_issue_cites(text)

    # Then  both cites are untouched
    assert "`Not covered: bare cites hold the close (#1234)`" in out, out
    assert "- a fence bullet that names #1235" in out, out
    assert f"{BASE}/issues/1234" not in out and f"{BASE}/issues/1235" not in out, out


def test_pointer_findings_reports_only_the_deferral_list_bullets():
    """issue #3055: the seam can tell a bare pointer from every other cite, which is what lets a body
    be checked without a hand-built regex at each call site.
    """

    # Given a body that DIDN'T come from the renderer: a bare pointer plus cites elsewhere
    hand_written = (
        "## Problem\n\nthe umbrella (#1000) left its own lane open.\n\n"
        "## Not covered\n\n"
        "- the engine-bump lane is its own issue #3050\n"
        f"- the trend lane is tracked as {BASE}/issues/3056\n\n"
        "## Technical\n\n`scripts/check_pr_acceptance.py` read `bare cites hold the close (#1234)`.\n"
    )

    # When  the pointer reader runs over it
    findings = ib.pointer_findings(hand_written)

    # Then  exactly the one bare pointer is reported, and it names the remedy
    assert len(findings) == 1, findings
    assert "#3050" in findings[0], findings[0]
    assert "Not covered" in findings[0], findings[0]
    assert "3056" not in findings[0] and "1234" not in findings[0], findings[0]


def test_the_gate_wording_quoted_in_technical_is_not_a_pointer():
    """issue #3055: the finding text the gates print (`Not covered: bare cites hold the close (#1234)`)
    is safe to record in an issue body verbatim — quoting the remedy never creates a new lane.
    """

    # Given a body whose Technical quotes the finding and whose deferral list is correct
    body = _body(
        technical=[
            "`scripts/check_pr_acceptance.py`: `Not covered: bare cites hold the close (#1234) "
            "— defer them as full issue URLs`",
        ],
        not_covered=["the retro-fit sweep is its own issue (#3053)"],
    )

    # Then  no pointer is reported anywhere in the body, and the quoted cite stayed bare
    assert ib.pointer_findings(body) == [], ib.section_body(body, "Not covered")
    assert "(#1234)" in ib.section_body(body, "Technical"), body
    assert f"{BASE}/issues/1234" not in body, body
    assert f"{BASE}/issues/3053" in ib.section_body(body, "Not covered"), body


def test_issue_url_is_the_tracker_form_the_gates_and_bodies_share():
    """issue #3055: one place spells the tracker URL, so an issue body, a PR body and a gate's remedy
    text cannot disagree about what a full issue reference looks like.
    """

    assert ib.issue_url(3055) == f"{BASE}/issues/3055"
    assert ib.issue_url("3055") == f"{BASE}/issues/3055"
    assert ib.link_issue_cites("tracked as #3055") == f"tracked as {BASE}/issues/3055"
