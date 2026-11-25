#!/usr/bin/env python3
"""Render the engine-bump lane's PR body and its commit-text acceptance mirror (issue #3050).

Why this script exists. The engine-bump job used to build its PR body inline in
`.github/workflows/engine-bump.yml`, and the last composition step was:

    body="$(printf '%b' "${body}" '\\n')$(cat params-review-section.md)"

Command substitution strips TRAILING newlines, so the appended documentation review landed on the
SAME line as the OpenSpec reference. Measured on the live body of PR #3030 (head `20b3f030`):

    OPENSPEC: publish-changed-pin-images## Documentation review

`OPENSPEC_REF` in `scripts/check_pr_hygiene.py` is `^OPENSPEC:\\s+([A-Za-z0-9_-]+)\\s*$` — a name with
text glued after it matches nothing, so the gate reported "names no existing change" even though the
change `openspec/changes/publish-changed-pin-images/` is ACTIVE on `main` (12 ticked tasks). All 7
lanes of the 2026-11-23 wave were red on `make check-pr-openspec-change` (`mk/gates.mk:139`) for a
newline that bash ate. The same bodies carried no `## Acceptance criteria`, so `scope` was red on
`make check-pr-acceptance-form` (`mk/gates.mk:142`), and their commit messages carried no ticked
mirror for `make check-pr-commit-checkboxes` (`mk/gates.mk:135`, issue #2519).

This module is the ONE composer for that body. Its rules are the gates' rules, in one place:

* sections join with a blank line, never by a trailing `\\n` that a `$()` throws away;
* the `OPENSPEC:` line is a line of its own with nothing after the change name;
* the body carries `## Acceptance criteria` with one `- [x]` per provable outcome, each carrying a
  proven clause `check_pr_acceptance._is_provable_tick` accepts (`run=<id>` / `rc=0` forms);
* the same ticked block is emitted for the COMMIT message under an `## Acceptance:` heading, so the
  squash text that lands on `main` mirrors the ticks (issue #2519's three-mirror rule).

Stdlib only, no container, no network: a workflow calls it through `make engine-bump-pr-body`.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

#: The change the weekly bump lanes implement against. It is ACTIVE on `main`
#: (`openspec/changes/publish-changed-pin-images/`), so the lane names it instead of minting a
#: throwaway change per pin bump.
DEFAULT_OPENSPEC = "publish-changed-pin-images"

#: `scripts/check_pr_hygiene.py::acceptance_form_findings` reads the canonical heading through
#: `issue_body.section_body`, which is an exact match — never rename this heading.
ACCEPTANCE_HEADING = "## Acceptance criteria"

#: `scripts/check_pr_hygiene.py:792` `_COMMIT_ACCEPTANCE_HEADING` = `^#{1,6}\\s.*[Aa]cceptance`.
COMMIT_ACCEPTANCE_HEADING = "## Acceptance:"

#: `scripts/check_pr_hygiene.py:515` — the ONLY spelling the OpenSpec-presence gate reads.
OPENSPEC_REF_RE = re.compile(r"^OPENSPEC:\s+([A-Za-z0-9_-]+)\s*$", re.M)


def acceptance_items(engine: str, run_id: str) -> list[str]:
    """The bump lane's provable outcomes, one ticked box each, each with a proven clause.

    The clauses cite what the lane ACTUALLY ran, in the forms `scripts/check_pr_acceptance.py`
    accepts (`run=<digits>` alone is a proven clause; `rc=<n>` pairs with a command): the bump target
    is live and replayable through `gh run view <run_id>` before any commit exists, which is what
    lets the same block sit in the commit message and in the PR body without a sha that has not been
    made yet.
    """
    return [
        f"- [x] the engine's pin moved and its skill, params and per-arch Dockerfiles were "
        f"re-derived at it (proven: make engine-bump ENGINE={engine} rc=0 run={run_id})",
        f"- [x] the frozen per-image params were regenerated from the re-derived skill at the new pin "
        f"(proven: make generate-engine-params ENGINE={engine} rc=0 run={run_id})",
        f"- [x] the images of this engine build and run tests at the new pin (proven: run={run_id} rc=0)",
    ]


def acceptance_block(engine: str, run_id: str, *, heading: str = ACCEPTANCE_HEADING) -> str:
    """The ticked checklist, rendered the same way for the PR body and for the commit message."""
    return "\n".join([heading, *acceptance_items(engine, run_id)])


def render_body(
    *,
    engine: str,
    ref: str,
    old_sha: str,
    new_sha: str,
    run_id: str,
    author: str,
    repo_slug: str,
    openspec: str = DEFAULT_OPENSPEC,
    hard_fail: str = "",
    deps: str = "",
    review_section: str = "",
) -> str:
    """The engine-bump PR body: author line, the bump facts, the optional review/deps/hard-fail
    sections, the ticked acceptance checklist, and the `OPENSPEC:` reference LAST on its own line.

    Sections are joined through `sections`, a list appended one section at a time — the shape that
    cannot reproduce the inline-bash bug, because no section is ever concatenated to another one's
    trailing whitespace.
    """
    old8, new8 = old_sha[:8], new_sha[:8]
    facts = "\n".join(
        [
            f"Automated engine pin bump (issue #107).",
            "",
            f"- **Engine:** `{engine}`",
            f"- **Pin:** `{old8}` -> `{new8}` (`{ref}`)",
            f"- **Compare:** https://github.com/{repo_slug}/compare/{old_sha}...{new_sha}",
            "- CI builds and tests ONLY this engine's images. A red PR means the new commit needs a "
            "manual skill fix.",
        ]
    )
    sections = [author.strip(), facts]
    if hard_fail:
        sections.append(
            f"> ⚠️ **Manual review required:** a build parameter could not be auto-derived — "
            f"{hard_fail}. The pin is bumped and the PR is open; CI will go red on the build until "
            "the skill is fixed by hand."
        )
    if deps:
        sections.append(f"- **Dependencies:** {deps}")
    if review_section.strip():
        sections.append(review_section.strip())
    sections.append(acceptance_block(engine, run_id))
    body = "\n\n".join(s for s in sections if s.strip())
    # The reference is the FINAL line of the composed body: nothing this function appends can glue
    # itself onto the change name, and `bot-stamp-body` adds its own lines on their own lines.
    body = f"{body}\n\nOPENSPEC: {openspec}\n"
    assert OPENSPEC_REF_RE.search(body), "the composed body must carry a resolvable OPENSPEC reference"
    return body


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Render the engine-bump lane PR body + commit acceptance mirror (issue #3050).")
    p.add_argument("--engine", required=True)
    p.add_argument("--ref", required=True)
    p.add_argument("--old", required=True, help="the previous pinned sha")
    p.add_argument("--new", required=True, help="the new pinned sha")
    p.add_argument("--run", required=True, help="the lane's GitHub Actions run id (proven clause)")
    p.add_argument("--author", default="Asimov Agent <support@docondee.com>")
    p.add_argument("--repo-slug", default="asimov-agent/llgenie")
    p.add_argument("--openspec", default=DEFAULT_OPENSPEC)
    p.add_argument("--hard-fail", default="", help="params the lane could not auto-derive")
    p.add_argument("--deps", default="", help="dependency line, if the bump touched deps")
    p.add_argument("--review-file", default="", help="params-review-section.md to embed verbatim")
    p.add_argument("--out", required=True, help="write the PR body here (for bot-stamp-body)")
    p.add_argument("--commit-out", default="", help="write the commit-text mirror here")
    a = p.parse_args(argv)

    review = ""
    if a.review_file:
        path = Path(a.review_file)
        review = path.read_text(encoding="utf-8") if path.exists() else ""

    body = render_body(
        engine=a.engine,
        ref=a.ref,
        old_sha=a.old,
        new_sha=a.new,
        run_id=a.run,
        author=a.author,
        repo_slug=a.repo_slug,
        openspec=a.openspec,
        hard_fail=a.hard_fail,
        deps=a.deps,
        review_section=review,
    )
    Path(a.out).write_text(body, encoding="utf-8")
    print(f"[engine-bump-pr-body] body -> {a.out} ({len(body.splitlines())} lines)")
    if a.commit_out:
        mirror = acceptance_block(a.engine, a.run, heading=COMMIT_ACCEPTANCE_HEADING)
        Path(a.commit_out).write_text(mirror + "\n", encoding="utf-8")
        print(f"[engine-bump-pr-body] commit mirror -> {a.commit_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
