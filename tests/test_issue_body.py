"""The one issue shape: six sections, in order, `## Technical` last, acceptance criteria tickable.

Everything here is the real module — `render` and `missing` are the product, and the producers below
are the real functions, called with real findings/rows. No stand-in is needed: nothing in
`scripts/issue_body.py` talks to the network or to `gh`.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

from scripts import issue_body
from scripts import security_issues as si

FIELDS = dict(
    problem="the scanner reports a known-vulnerable pin",
    why="every build ships it and the scan re-reports it on every run",
    how=["move the pin", "let the pipeline re-scan"],
    benefit="the shipped dependency is no longer known-vulnerable",
    acceptance=["the scanner no longer reports it"],
    technical=["`tools/requirements.in`"],
)


def test_the_six_sections_render_in_order_with_technical_last():
    """The shape is positional: a reader learns the goal before any file path appears."""

    # Given the renderer's plain fields
    # When  a body is rendered
    body = issue_body.render(**FIELDS)

    # Then  the headings are the six sections, in order, and Technical is last
    assert issue_body.headings(body) == [
        "Problem", "Why it matters", "How we fix it", "Benefit", "Acceptance criteria", "Technical"]
    assert issue_body.missing(body) == []


def test_a_missing_section_is_named():
    """A body without its benefit is not a work item a reviewer can judge."""

    # Given a rendered body with the `## Benefit` heading stripped out
    body = issue_body.render(**FIELDS).replace("## Benefit", "## What it buys")

    # When  the checker reads it
    problems = issue_body.missing(body)

    # Then  it names the missing section rather than passing on a near-miss
    assert any("Benefit" in p for p in problems), problems


def test_technical_must_be_last():
    """The one technical section is the LAST one: the readable goal comes first."""

    # Given a body whose Technical section was moved to the front
    body = issue_body.render(**FIELDS)
    head, _, tail = body.partition("## Technical")
    moved = tail.strip().split("\n\n")[0]
    broken = f"## Technical\n\n{moved}\n\n{head}".rstrip() + "\n"

    # When  the checker reads it
    problems = issue_body.missing(broken)

    # Then  the order defect is named
    assert any("LAST" in p or "out of order" in p for p in problems), problems


def test_not_covered_precedes_technical():
    """Out-of-scope work is its own list, and it never displaces the technical section."""

    # Given a body with a deferred item
    body = issue_body.render(**FIELDS, not_covered=["syft has no image (#746)"])

    # When  the headings are read
    heads = issue_body.headings(body)

    # Then  Not covered sits between the acceptance criteria and Technical
    assert heads == ["Problem", "Why it matters", "How we fix it", "Benefit", "Acceptance criteria",
                     "Not covered", "Technical"]
    assert issue_body.missing(body) == []
    assert "#746" in issue_body.section_body(body, "Not covered")


def test_acceptance_criteria_must_be_tickable():
    """A heading with no `- [ ]` item states no "done", so it is a defect."""

    # Given a body whose acceptance section is prose with no checkbox
    body = issue_body.render(**FIELDS).replace(
        "- [ ] the scanner no longer reports it", "it should be better")

    # When  the checker reads it
    problems = issue_body.missing(body)

    # Then  it names the missing tickable criterion
    assert any("Acceptance criteria" in p and "- [ ]" in p for p in problems), problems


def test_render_requires_acceptance():
    """The renderer refuses to produce a body that states no acceptance criteria."""

    # Given the renderer's fields with acceptance withheld
    fields = dict(FIELDS)
    fields.pop("acceptance")

    # When  the render is attempted
    # Then  it raises, exactly as it does for a missing problem/why/benefit
    with pytest.raises(ValueError, match="acceptance"):
        issue_body.render(**fields)


def test_render_requires_problem_why_benefit():
    """The four readable sections are required fields, not optional prose."""

    # Given every field, one readable section at a time withheld
    for name in ("problem", "why", "benefit"):
        fields = dict(FIELDS)
        fields.pop(name)

        # When  the render is attempted
        # Then  it raises and names the missing field
        with pytest.raises(ValueError, match=name):
            issue_body.render(**fields)


def test_a_multiline_technical_item_stays_a_block_not_a_bullet():
    """A fenced log in `## Technical` is pasted as a block: `- ` before a fence turns it into prose."""

    # Given a technical detail that is a fenced, multi-line report
    body = issue_body.render(**{**FIELDS, "technical": ["label: `linux`", "```\nROW1\nROW2\n```"]})

    # When  the section is read
    text = issue_body.section_body(body, "Technical")

    # Then  the report is fenced and its rows are not each turned into a bullet
    assert "- label: `linux`" in text
    assert "```\nROW1\nROW2\n```" in text
    assert "- ROW1" not in text
    assert issue_body.missing(body) == []


def test_the_marker_round_trips():
    """The marker is a producer's idempotency key, so it stays the first line, byte for byte."""

    # Given a security finding (its marker is `<!-- security-finding: ... -->`)
    finding = si.Finding("CVE-1", "numpy", "1.0", "1.1", "critical", "trivy")

    # When  the real producer renders the body
    body = si.body_for(finding)

    # Then  the marker is the first line and `MARKER_RE` still finds the same key
    assert body.splitlines()[0] == finding.marker
    m = si.MARKER_RE.search(body)
    assert (m.group(1), m.group(2), m.group(3)) == ("trivy", "CVE-1", "numpy")
    assert [h for h in issue_body.headings(body) if h in issue_body.SECTIONS] == \
        list(issue_body.SECTIONS)
    assert issue_body.missing(body) == []


def test_every_producer_renders_tickable_criteria():
    """Each real producer's body carries the shape, including tickable acceptance criteria."""

    # Given one real payload per producer family
    import code_review
    import engine_skill_gap
    import registry_change_issue
    import run_failure_reactor

    finding = si.Finding("CVE-1", "numpy", "1.0", "1.1", "critical", "trivy")
    review = {"key": "workflow-never-ran/.github/workflows/x.yml", "evidence": "it never ran",
              "where": ".github/workflows/x.yml"}
    run = {"workflowName": "CI", "displayTitle": "CI / unit", "event": "push", "headSha": "a" * 40}
    job = {"name": "unit", "steps": [{"name": "make test-unit", "conclusion": "failure"}]}
    gap = {"engines": {"vllm": {"models": []}}, "models_never_offered": []}
    registry = {"engines": {"vllm": {"backend": "cuda", "url": "https://example.invalid"}}}
    change = {
        "utc_before": "2026-10-20T00:00:00Z", "utc_after": "2026-10-27T00:00:00Z",
        "models_before": 2, "models_after": 3, "engines_before": 1, "engines_after": 1,
        "catalog_before": {"models": 2, "links": 2}, "catalog": {"models": 3, "links": 3},
        "matrix_cases": 1, "unresolved_engines": 0, "changed": ["data/models.json"],
        "added_models": [{"id": "m", "name": "M", "vram_tier": 8}], "removed_models": [],
        "renamed_models": [], "new_engines": [], "contract_changed": False,
        "row_required_added": [], "row_required_removed": [], "backend_enum_added": [],
        "readme_rows_before": 2, "readme_rows_after": 3, "readme_added": ["M"],
        "readme_removed": [], "formats_before": ["GGUF"], "formats_after": ["GGUF"],
        "prev_rev": "HEAD",
    }

    # When  every producer renders its body
    bodies = {
        "security_issues": si.body_for(finding, "https://example.invalid/run/1"),
        "code_review": code_review.issue_body(review),
        "run_failure_reactor": run_failure_reactor.issue_body(run, job, "tail", "<!-- r -->"),
        "engine_skill_gap": engine_skill_gap.issue_body("vllm", registry, gap),
        "registry_change_issue": registry_change_issue.render(change),
    }

    # Then  each carries the six sections and at least one tickable criterion
    for name, body in bodies.items():
        assert issue_body.missing(body) == [], (name, issue_body.missing(body))
        assert "- [ ]" in issue_body.section_body(body, "Acceptance criteria"), name
