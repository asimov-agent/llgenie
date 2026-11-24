#!/usr/bin/env python3
"""Every issue body this repository files carries the goal, then the technical solution (issue #745).

A reader who was not in the run that filed an issue must be able to answer four questions — what is
broken, why it matters, what the fix is, what it buys — before any file path appears. The PR body
already has that rule and a gate (`scripts/check_pr_hygiene.py`); the issue is one artifact earlier in
the pipeline, and it is what the implementer starts from. This gate makes the rule real:

  check_issue_body.py check    exit 1 on any defect below
  check_issue_body.py report   print the producer roster, the skill state and the verdict

Findings:

- a producer in `scripts/issue_body.py::PRODUCERS` that does not import `issue_body` and call
  `issue_body.render(` — a second shape, which is the defect, not a style choice;
- a producer that writes a section heading (`## Problem`, `## Why it matters`, `## How we fix it`,
  `## Benefit`, `## Not covered`, `## Technical`) into its own source: the renderer is the one place
  those are spelled;
- `AGENTS.md` without the section that states the rule (so deleting the rule is a red gate, exactly
  as `check_pr_authors` treats its own section);
- `.hermes/skills/issue-triage/SKILL.md` or `.hermes/skills/issue-refiner/SKILL.md` no longer naming
  the five sections in their `REFINED:` / `RESTATED:` output block;
- a producer whose `## Not covered` pointer survives the renderer as a bare `#<n>` cite: a bare cite is
  the token `check_pr_acceptance.rollout_lane_findings` reads as a rollout lane, so an umbrella's own
  deferral list is what blocks its `closes #<umbrella>` (issue #3055);
- a renderer whose own output does not pass its own `missing()` (the renderer and the checker must
  agree, or the gate proves nothing).

Stdlib only: `make ci-unit` runs it on a bare host.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import issue_body  # noqa: E402  (the module under test, from the repo's own scripts/)

AGENTS = "AGENTS.md"
#: The heading `AGENTS.md` MUST carry (a prefix match: the section title may be reworded after it).
AGENTS_HEADING = "## Every issue carries the problem, why, the fix and the benefit"
SKILLS = (".hermes/skills/issue-triage/SKILL.md", ".hermes/skills/issue-refiner/SKILL.md")
#: A section heading spelled as a quoted string — how a producer would BUILD a body instead of
#: rendering it (`"## Problem"`, `f"## {x}"` does not match because the name is interpolated). A
#: mention inside prose (``the `## Technical` detail``) is backtick-quoted, not a second shape.
QUOTED_HEADING_RE = re.compile(
    r"""["']## (?:""" + "|".join(re.escape(n) for n in issue_body.SECTIONS
                                + (issue_body.OPTIONAL_SECTION,)) + r""")["']""")
#: Every spelling a producer may use to reach the renderer (see `_renders`).
RENDER_CALLS: tuple[str, ...] = ("issue_body.render(", "render_body(")


def _read(rel: str, root: Path) -> str:
    path = root / rel
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _renders(text: str) -> bool:
    """Does this producer call the renderer? `code_review.issue_body` names its own function
    `issue_body`, so it imports the renderer as `render_body` — the rule is "through the seam", not
    one spelling of it."""
    return any(call in text for call in RENDER_CALLS)


def check_producer(rel: str, fn: str, root: Path) -> list[str]:
    """One producer: it must render through the seam and must not spell a section itself."""
    text = _read(rel, root)
    if not text:
        return [f"{rel}: missing — the producer roster names it"]
    out: list[str] = []
    if not re_imports_issue_body(text):
        out.append(f"{rel}: does not import `issue_body` — `{fn}` must render through it")
    if not _renders(text):
        out.append(f"{rel}: `{fn}` never calls the renderer ({' or '.join(RENDER_CALLS)}) — a "
                   "hand-built body is a second shape (issue #745)")
    for _ in QUOTED_HEADING_RE.findall(text):
        out.append(f"{rel}: writes a `##` section of its own — the sections are spelled only in "
                   "scripts/issue_body.py (issue #745)")
        break
    return out


def re_imports_issue_body(text: str) -> bool:
    return ("import issue_body" in text) or ("from issue_body import" in text)


#: The argument a producer passes its deferred pointers in (issue #3055).
NOT_COVERED_KW = "not_covered="
#: A bare-cite spelling in a producer's `not_covered=` region: `(#669)` or an interpolated `#{n}`.
BARE_CITE_SPELLING_RE = re.compile(r"#(?:\d+|\{[^}]*\})")
#: The number a probe bullet cites. The probe sends the producer's pointer through the renderer, so the
#: gate measures the producer+renderer pair instead of trusting either one's prose.
PROBE_CITE = "3055"


def _not_covered_regions(text: str) -> list[str]:
    """Each `not_covered=` argument in a producer source, brackets matched."""
    regions: list[str] = []
    for m in re.finditer(re.escape(NOT_COVERED_KW), text):
        i = m.end()
        while i < len(text) and text[i] in " \n\t":
            i += 1
        if i >= len(text) or text[i] not in "[(":
            continue
        depth, j = 0, i
        while j < len(text):
            if text[j] in "([{":
                depth += 1
            elif text[j] in ")]}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        regions.append(text[i:j + 1])
    return regions


def _pointer_probe_body() -> str:
    """A body whose only `## Not covered` pointer is a bare cite, rendered through the one seam."""
    return issue_body.render(
        problem="an umbrella defers side work and names it with a bare cite",
        why="the bare cite is the token the acceptance rollout path reads as a lane, and it holds the "
            "umbrella's own close",
        how=["render the deferred pointer as its full issue URL through the one seam"],
        benefit="the umbrella's PR carries its `closes` while the side issue stays open",
        acceptance=["`make check-issue-bodies` re-renders the pointer and links it"],
        technical=["`scripts/issue_body.py::link_issue_cites`"],
        not_covered=[f"the deferred lane is its own issue #{PROBE_CITE}"],
    )


def check_pointer_shape(rel: str, root: Path) -> list[str]:
    """A producer's deferred pointer must survive the renderer as a URL (issue #3055)."""
    regions = _not_covered_regions(_read(rel, root))
    if not any(BARE_CITE_SPELLING_RE.search(region) for region in regions):
        return []
    body = _pointer_probe_body()
    section = issue_body.section_body(body, issue_body.OPTIONAL_SECTION)
    out = [f"{rel}: its `Not covered` pointer survives the renderer — {p}"
           for p in issue_body.pointer_findings(body)]
    if not out and f"{issue_body.ISSUE_URL_BASE}/issues/{PROBE_CITE}" not in section:
        out.append(f"{rel}: its `Not covered` pointer is not rendered as "
                   f"{issue_body.ISSUE_URL_BASE}/issues/<n> (issue #3055)")
    return out


def check_agents(root: Path) -> list[str]:
    text = _read(AGENTS, root)
    if not text:
        return [f"{AGENTS}: missing"]
    out: list[str] = []
    if AGENTS_HEADING not in text:
        out.append(f"{AGENTS}: the section `{AGENTS_HEADING}` is gone — the rule that an issue "
                   "states the problem, why, the fix and the benefit, then a technical solution, "
                   "must not be deletable silently (issue #745)")
    for name in issue_body.SECTIONS:
        if f"`## {name}`" not in text and f"## {name}" not in text:
            out.append(f"{AGENTS}: the section does not name `## {name}`")
    return out


def check_skills(root: Path) -> list[str]:
    out: list[str] = []
    for rel in SKILLS:
        text = _read(rel, root)
        if not text:
            out.append(f"{rel}: missing — the issue legs must state the shape themselves")
            continue
        absent = [n for n in issue_body.SECTIONS if f"## {n}" not in text]
        if absent:
            out.append(f"{rel}: does not name {', '.join('`## ' + n + '`' for n in absent)} — the "
                       "restatement it writes must carry the same six sections (issue #745)")
    return out


def check_renderer() -> list[str]:
    """The renderer's own output must pass its own checker — otherwise the gate is decoration."""
    body = issue_body.render(
        problem="a producer files a body nobody can act on",
        why="the implementer starts from it and the PR has to restate a goal that was never written",
        how=["render through the one seam", "check it in ci-unit"],
        benefit="every issue says what, why, how and what it buys before any file path",
        acceptance=["`make check-issue-bodies` names a hand-built body", "the six sections render "
                    "in order with `## Technical` last"],
        technical=["`scripts/issue_body.py`", "`make check-issue-bodies`"],
        not_covered=["retro-fitting the open issues", "the lane is its own issue #3055"],
        marker="<!-- test-marker -->",
    )
    out = [f"scripts/issue_body.py: renders a body its own checker refuses — {p}"
           for p in issue_body.missing(body)]
    out += [f"scripts/issue_body.py: {p}" for p in issue_body.pointer_findings(body)]
    if not out and f"{issue_body.ISSUE_URL_BASE}/issues/3055" not in issue_body.section_body(
            body, issue_body.OPTIONAL_SECTION):
        out.append("scripts/issue_body.py: a bare `#3055` pointer in `## Not covered` was not rendered "
                   "as its full issue URL (issue #3055)")
    if not out and not body.startswith("<!-- test-marker -->"):
        out.append("scripts/issue_body.py: the marker is no longer the first line — every producer's "
                   "dedupe reads it back (issue #745)")
    return out


def check(root: Path = REPO) -> list[str]:
    findings: list[str] = []
    for rel, fn in issue_body.PRODUCERS:
        findings += check_producer(rel, fn, root)
        findings += check_pointer_shape(rel, root)
    findings += check_agents(root)
    findings += check_skills(root)
    findings += check_renderer()
    return findings


def report(root: Path = REPO) -> int:
    print(f"[issue-body] shape: {' -> '.join('## ' + n for n in issue_body.SECTIONS)}")
    print(f"[issue-body] {len(issue_body.PRODUCERS)} producer(s):")
    for rel, fn in issue_body.PRODUCERS:
        text = _read(rel, root)
        state = "renders" if _renders(text) else "HAND-BUILT"
        print(f"  {state:10s} {rel}::{fn}")
    print(f"[issue-body] {AGENTS}: "
          f"{'states the rule' if AGENTS_HEADING in _read(AGENTS, root) else 'SECTION MISSING'}")
    for rel in SKILLS:
        text = _read(rel, root)
        absent = [n for n in issue_body.SECTIONS if f"## {n}" not in text]
        print(f"  {rel}: {'states the shape' if not absent else 'missing ' + ', '.join(absent)}")
    findings = check(root)
    if findings:
        print(f"[issue-body] {len(findings)} problem(s):")
        for item in findings:
            print(f"  - {item}")
        return 1
    print("[issue-body] OK: every producer renders through the one seam, the sections are in order "
          "with `## Technical` last, and the rule is stated in AGENTS.md and both issue skills")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Every issue states the goal, then the technical "
                                             "solution (issue #745)")
    ap.add_argument("cmd", choices=("check", "report"))
    ap.add_argument("--root", default=str(REPO))
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    return report(root) if args.cmd == "report" else (0 if not check(root) else 1)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
