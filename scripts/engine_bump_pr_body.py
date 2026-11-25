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


#: The bump lane's provable outcomes as CLAIMS (issue #3054). The composer attaches a `(proven: …)`
#: clause to each; `make engine-bump-restamp` re-cites the SAME claims with the evidence it read at the
#: live head. A claim is what the guarded write seam (`scripts/pr_body_write.py`, issue #2131) protects;
#: a clause is what a restamp renews, because a clause recorded at another head is a finding (#2288).
ACCEPTANCE_CLAIMS: tuple[str, ...] = (
    "the engine's pin moved and its skill, params and per-arch Dockerfiles were re-derived at it",
    "the frozen per-image params were regenerated from the re-derived skill at the new pin",
    "the images of this engine build and run tests at the new pin",
)


def acceptance_items(engine: str, run_id: str, *, head_sha: str = "",
                     image_runs: tuple[str, ...] = ()) -> list[str]:
    """The bump lane's provable outcomes, one ticked box each, each with a proven clause.

    The clauses cite what the lane ACTUALLY ran, in the forms `scripts/check_pr_acceptance.py`
    accepts (`run=<digits>` alone is a proven clause; `rc=<n>` pairs with a command). Two measured
    constraints shape them (issue #2288, `check_pr_acceptance.py:549-590`):

    - the cited run must be readable through `gh api repos/<repo>/actions/runs/<id>`. A `gh pr
      checks` id is a check SUITE id, not a workflow run id — the suite id #3029's clauses cited
      (`137942170961`) 404s there, which the gate reports as `tick-run-unreadable`. Pass
      `github.run_id` (or a check run's `html_url` run number) as `run_id`/`image_runs`.
    - a green proof recorded at another head must flag the live head, or the gate reports
      `tick-stale-head-unflagged`. Pass `head_sha` (the bump commit this PR carries) so every
      clause names it.
    """
    at_head = f" {head_sha}" if head_sha else ""
    images = " ".join(f"run={r}" for r in image_runs) or f"run={run_id} rc=0"
    clauses = (
        f"make engine-bump ENGINE={engine} rc=0 run={run_id}{at_head}",
        f"make generate-engine-params ENGINE={engine} rc=0 run={run_id}{at_head}",
        f"{images}{at_head}",
    )
    return [f"- [x] {claim} (proven: {clause})"
            for claim, clause in zip(ACCEPTANCE_CLAIMS, clauses)]


def acceptance_block(engine: str, run_id: str, *, heading: str = ACCEPTANCE_HEADING,
                     items: list[str] | None = None, head_sha: str = "",
                     image_runs: tuple[str, ...] = ()) -> str:
    """The ticked checklist, rendered the same way for the PR body and for the commit message.

    `items` lets a caller that MEASURED the evidence (the `make engine-bump-restamp` leg reads the
    live head, the params/skill files and the image check runs) supply its own ticked boxes instead
    of the lane's at-compose-time assumptions; the composer remains the only renderer.
    """
    return "\n".join([heading, *(items or acceptance_items(engine, run_id,
                                                           head_sha=head_sha,
                                                           image_runs=image_runs))])


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
    head_sha: str = "",
    image_runs: tuple[str, ...] = (),
    acceptance_items: list[str] | None = None,
    not_covered: tuple[str, ...] = (),
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
    sections.append(acceptance_block(engine, run_id, items=acceptance_items, head_sha=head_sha,
                                     image_runs=image_runs))
    if not_covered:
        sections.append("\n".join(["## Not covered", "", *not_covered]))
    body = "\n\n".join(s for s in sections if s.strip())
    # The reference is the FINAL line of the composed body: nothing this function appends can glue
    # itself onto the change name, and `bot-stamp-body` adds its own lines on their own lines.
    body = f"{body}\n\nOPENSPEC: {openspec}\n"
    assert OPENSPEC_REF_RE.search(body), "the composed body must carry a resolvable OPENSPEC reference"
    return body


def _read_lines_file(path: str) -> list[str]:
    """One ticked item per non-blank line of a file (the restamp leg writes what it measured)."""
    return [ln for ln in Path(path).read_text(encoding="utf-8").splitlines() if ln.strip()]


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
    p.add_argument("--head", default="", help="the bump commit this PR carries; every proven clause "
                                              "names it (issue #2288 head rule)")
    p.add_argument("--image-run", action="append", default=[],
                   help="a READABLE green engine-build workflow run id (NOT a `gh pr checks` suite id)")
    p.add_argument("--not-covered", action="append", default=[],
                   help="an out-of-scope line; each one must name its own linked issue")
    p.add_argument("--items-file", default="", help="file of measured ticked items; when given, the "
                                                    "PR body AND the commit mirror render THESE items")
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
        head_sha=a.head,
        image_runs=tuple(a.image_run),
        acceptance_items=_read_lines_file(a.items_file) if a.items_file else None,
        not_covered=tuple(a.not_covered),
    )
    Path(a.out).write_text(body, encoding="utf-8")
    print(f"[engine-bump-pr-body] body -> {a.out} ({len(body.splitlines())} lines)")
    if a.commit_out:
        # The commit mirror carries the SAME items the body carries, under the commit heading — the
        # text mirror gate (#2908) compares the two, so a measured item set must appear in both.
        mirror = acceptance_block(a.engine, a.run, heading=COMMIT_ACCEPTANCE_HEADING,
                                  head_sha=a.head, image_runs=tuple(a.image_run),
                                  items=_read_lines_file(a.items_file) if a.items_file else None)
        Path(a.commit_out).write_text(mirror + "\n", encoding="utf-8")
        print(f"[engine-bump-pr-body] commit mirror -> {a.commit_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
