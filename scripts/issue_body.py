#!/usr/bin/env python3
"""One shape for every issue body this repository files (issue #745).

An issue is the root of the pipeline — issue -> branch -> OpenSpec change -> code -> PR -> `closes #n`,
and AGENTS.md says a work item's GOAL lives in the issue. The PR body is gated
(`scripts/check_pr_hygiene.py` refuses one without `Issue: / Fix: / Benefit: / Technical:`); an issue
body was gated by nothing, so the seven producers below each invented a shape and a reader who was not
in the run that filed the issue could not say what was broken, why it mattered, or what the fix buys.

This module is the ONE renderer. A producer supplies plain fields and gets:

    ## Problem              what is wrong, observed — the measured symptom
    ## Why it matters       the consequence of leaving it
    ## How we fix it        numbered, plain language, no file paths
    ## Benefit              what the reader gets once it is fixed
    ## Acceptance criteria  tickable `- [ ]` items: what "done" looks like, provable
    ## Not covered          optional: each deferred item names its own issue
    ## Technical            LAST and only here: files, targets, tests, gates, measured numbers

The producer's dedupe marker is the body's FIRST line, byte for byte, because every producer's
idempotence reads it back (`MARKER_RE` in security_issues, `filed()` in code_review and
run_failure_reactor, the marker search in registry_change_issue, `label_marker` in queued_run_alarm).
Restructuring a body must never cost a producer its memory of what it filed.

The mapping to the PR body is stated in AGENTS.md so the two cannot drift: `Problem` <-> `Issue:`,
`How we fix it` <-> `Fix:`, `Benefit` <-> `Benefit:`, `Technical` <-> `Technical:`.

Stdlib only: the unit suite imports this module on a bare host.
"""
from __future__ import annotations

import re

#: The six required sections, in order. `Technical` is last by construction.
SECTIONS: tuple[str, ...] = ("Problem", "Why it matters", "How we fix it", "Benefit",
                             "Acceptance criteria", "Technical")
#: The optional section, allowed anywhere between `Benefit` and `Technical`.
OPTIONAL_SECTION = "Not covered"
#: The checkbox a criterion is written as: a sentence a reviewer can tick.
CHECKBOX = "- [ ]"
#: Every producer that files an issue, and the function that builds its body. `check_issue_body`
#: reads these source files: a body built without `render` here is the defect.
PRODUCERS: tuple[tuple[str, str], ...] = (
    ("scripts/security_issues.py", "body_for"),
    ("scripts/code_review.py", "issue_body"),
    ("scripts/run_failure_reactor.py", "issue_body"),
    ("scripts/engine_skill_gap.py", "issue_body"),
    ("scripts/registry_change_issue.py", "render"),
    ("scripts/architecture_bot.py", "render_issue"),
    ("scripts/queued_run_alarm.py", "file_label_issue"),
    ("scripts/jev_preflight_tracker.py", "issue_body"),
    ("scripts/trend_staleness_issue.py", "render_issue"),
    ("scripts/check_agent_model_catalog.py", "issue_text"),
)
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.M)
#: The tracker every issue in this repository lives in (issue #3055).
ISSUE_URL_BASE = "https://github.com/asimov-agent/llgenie"
#: A BARE issue cite: `#123`. A letter after the `#` is a line/heading anchor (`file.py#L105`), and a
#: `#` glued to a word, a dot or a slash is part of that token (`x.py#1`, `/issues#1`) — never a cite.
BARE_CITE_RE = re.compile(r"(?<![\w/.])#(\d+)")


def issue_url(number) -> str:
    """The full URL of issue `number` (issue #3055): the shape a `## Not covered` pointer must carry."""
    return f"{ISSUE_URL_BASE}/issues/{str(number).lstrip('#').strip()}"


def link_issue_cites(text: str, base: str = ISSUE_URL_BASE) -> str:
    """Rewrite every bare `#<n>` in `text` as its full issue URL (issue #3055).

    Why the shape matters: `scripts/check_pr_acceptance.py::rollout_lane_findings` derives an
    umbrella's rollout lanes from the bare `#<n>` cites in the umbrella's OWN body, and an OPEN issue
    that cites the umbrella back holds the umbrella's `closes #<umbrella>` (`rollout-lane-open`).
    AGENTS.md wants every `## Not covered` item to name its own side issue — spelled as a bare cite,
    that deferral list is what blocks the umbrella's own close (#3053's PR was held by its pointer to
    #3050). A full `.../issues/<n>` link renders the same pointer and never triggers the cite.

    Preserved exactly: fenced blocks (```), inline `code` spans, line/heading anchors, and pointers
    that are already links — so a quoted gate message or a `file.py#L105` reference is not rewritten.
    """
    out: list[str] = []
    in_fence = False
    #: Numbers the text already names as an issue URL: rewriting `… /issues/3056 (issue #3056)` again
    #: would nest a link inside a link and leave the pointer unreadable (issue #3055).
    already = {m.group(1) for m in re.finditer(r"/issues/(\d+)", str(text))}

    def _link(m: re.Match, b: str = base) -> str:
        return m.group(0) if m.group(1) in already else f"{b}/issues/{m.group(1)}"

    for line in str(text).split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence:
            out.append(line)
            continue
        parts = line.split("`")
        for i in range(0, len(parts), 2):  # even segments are prose, odd segments are inline code
            parts[i] = BARE_CITE_RE.sub(_link, parts[i])
        out.append("`".join(parts))
    return "\n".join(out)


def _bullets(items) -> list[str]:
    if isinstance(items, str):
        items = [items]
    return [f"- {str(i).strip()}" for i in items]


def _link_bullets(items) -> list[str]:
    """`Not covered` bullets with every deferred pointer rendered as a full issue URL (issue #3055)."""
    return [link_issue_cites(b) for b in _bullets(items)]


def _numbered(items) -> list[str]:
    if isinstance(items, str):
        items = [items]
    return [f"{n}. {str(i).strip()}" for n, i in enumerate(items, start=1)]


def _criteria(items) -> list[str]:
    """Acceptance criteria are checkboxes: a criterion a reviewer cannot tick is not one.

    A criterion must be PROVABLE by a run or a command it does not itself gate (issue #2094): a box
    of the shape "the PR that fixes it is green in CI on the same job that failed" is UNPROVABLE when
    that job is the acceptance gate's own (`guard` / `check-pr-acceptance` / `ci-verdict` / `judge`),
    because the gate cannot pass until the box is ticked and the box cannot be proven until the gate
    passes — a closed loop that parks a finished PR forever (measured #2046/PR #2051). Name the run
    or command that proves the criterion WITHOUT riding on the gate's own verdict.
    """
    if isinstance(items, str):
        items = [items]
    out: list[str] = []
    for item in items:
        text = str(item).strip()
        out.append(f"{CHECKBOX} {text[len(CHECKBOX):].strip() if text.startswith(CHECKBOX) else text}")
    return out


def _technical(items) -> list[str]:
    """The technical detail: one bullet per fact, and a multi-line item (a fenced log or table) kept
    as a block — prefixing a fence with `- ` would produce a list that renders as prose."""
    if isinstance(items, str):
        items = [items]
    out: list[str] = []
    for item in items:
        text = str(item).strip()
        if "\n" in text:
            out += ["", text, ""]
        else:
            out.append(f"- {text}")
    return out


def render(*, problem: str = "", why: str = "", how=None, benefit: str = "", acceptance=None,
           technical=None, not_covered=None, marker: str | None = None) -> str:
    """Render one issue body in the repository's shape (issue #745).

    `problem`, `why` and `benefit` are paragraphs. `how` and `technical` are a string or a list of
    steps/bullets. `acceptance` is required: one `- [ ]` criterion per provable outcome, so "done"
    is a list a reviewer ticks instead of an adjective. `not_covered` is optional: one bullet per
    deferred item, and each should name the issue it was filed as (AGENTS.md: out-of-scope work is
    its own linked issue, never prose). Every bare `#<n>` in those bullets is rendered as its full
    issue URL (issue #3055): a bare cite is the token the acceptance rollout path reads as a lane, so
    a deferral list spelled with bare cites holds the umbrella's own `closes #<umbrella>`. `marker` is
    emitted unchanged as the first line, so a producer's dedupe still finds its issue.
    """
    for name, value in (("problem", problem), ("why", why), ("benefit", benefit)):
        if not str(value or "").strip():
            raise ValueError(f"[issue-body] `{name}` is required: an issue that does not state it "
                             "cannot be acted on by anyone but its author (issue #745)")
    for name, value in (("how", how), ("acceptance", acceptance), ("technical", technical)):
        if not (value if isinstance(value, str) else list(value or [])):
            raise ValueError(f"[issue-body] `{name}` is required (issue #745)")

    lines: list[str] = []
    if marker:
        lines += [str(marker).strip(), ""]
    lines += [
        "## Problem", "", str(problem).strip(), "",
        "## Why it matters", "", str(why).strip(), "",
        "## How we fix it", "", *_numbered(how), "",
        "## Benefit", "", str(benefit).strip(), "",
        "## Acceptance criteria", "", *_criteria(acceptance), "",
    ]
    if not_covered:
        lines += ["## " + OPTIONAL_SECTION, "", *_link_bullets(not_covered), ""]
    lines += ["## Technical", "", *_technical(technical)]
    return "\n".join(lines).rstrip("\n") + "\n"


def headings(text: str) -> list[str]:
    """Every `##` heading, in the order it appears."""
    return [m.group(1).strip() for m in HEADING_RE.finditer(text or "")]


def section_body(text: str, name: str) -> str:
    """The lines between `## <name>` and the next `##` heading (empty when the section is absent)."""
    lines = (text or "").splitlines()
    start = None
    for i, line in enumerate(lines):
        m = HEADING_RE.match(line)
        if m and m.group(1).strip() == name:
            start = i
            break
    if start is None:
        return ""
    rest = lines[start + 1:]
    end = next((i for i, line in enumerate(rest) if HEADING_RE.match(line)), len(rest))
    return "\n".join(rest[:end]).strip()


def pointer_findings(text: str) -> list[str]:
    """Every `## Not covered` bullet that still carries a bare `#<n>` cite (issue #3055).

    The renderer links pointers, so a body built through `render` never trips this. A body that
    DIDN'T (a hand-written umbrella, a producer that splices its own bullets) holds its own close:
    `scripts/check_pr_acceptance.py::rollout_lane_findings` reads a bare `#<n>` in the umbrella's body
    as a rollout lane and blocks the umbrella's `closes #<umbrella>` while that issue is OPEN. Cites
    inside fenced blocks or inline `code` (a quoted gate message) are not pointers and are not reported.
    """
    problems: list[str] = []
    for line in section_body(text, OPTIONAL_SECTION).splitlines():
        if not line.strip().startswith("- "):
            continue
        if line == link_issue_cites(line):
            continue
        cites = sorted({m.group(1) for m in BARE_CITE_RE.finditer(line)})
        if cites:
            problems.append(
                f"`## {OPTIONAL_SECTION}` names {', '.join('#' + c for c in cites)} as a bare cite — "
                f"a deferred pointer is its full issue URL ({ISSUE_URL_BASE}/issues/<n>); a bare cite "
                "is the token the acceptance rollout path reads as a lane, and it holds the "
                "umbrella's own `closes #<umbrella>` (issue #3055)")
    return problems


def missing(text: str) -> list[str]:
    """Every defect in `text` against the shape: absent, out of order, duplicated, or misplaced.

    Returns human-readable findings (empty means the body conforms). The order rule is positional, so
    a body that lists the sections in the wrong order is reported as such rather than as six missing
    sections. `## Acceptance criteria` must also carry at least one `- [ ]` item: a heading with no
    tickable criterion states no "done".
    """
    found = headings(text)
    problems: list[str] = []
    for name in SECTIONS:
        if name not in found:
            problems.append(f"`## {name}` is missing")
    if problems:
        return problems
    expected = list(SECTIONS)
    given = [n for n in found if n in SECTIONS]
    if given != expected:
        problems.append(f"the sections are out of order: {' -> '.join(given)} "
                        f"(expected {' -> '.join(expected)})")
    if found.count("Technical") > 1:
        problems.append("`## Technical` appears more than once")
    if found[-1] != "Technical":
        problems.append(f"`## Technical` must be the LAST section (it is followed by "
                        f"`## {found[-1]}`)")
    if CHECKBOX not in section_body(text, "Acceptance criteria"):
        problems.append(f"`## Acceptance criteria` carries no `{CHECKBOX}` item — what \"done\" looks "
                        "like must be a list a reviewer can tick (issue #745)")
    unknown = [n for n in found if n not in SECTIONS and n != OPTIONAL_SECTION]
    if unknown:
        problems.append("unknown section(s): " + ", ".join(f"`## {n}`" for n in unknown))
    if OPTIONAL_SECTION in found:
        at, benefit, technical = (found.index(OPTIONAL_SECTION), found.index("Benefit"),
                                  found.index("Technical"))
        if not benefit < at < technical:
            problems.append(f"`## {OPTIONAL_SECTION}` must sit between `## Benefit` and "
                            "`## Technical`")
    return problems
