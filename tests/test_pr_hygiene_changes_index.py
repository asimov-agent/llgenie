"""A `CHANGES.md` row must correspond to a `docs/changes.d/<stem>.md` fragment (issue #1063).

The change index is a directory of one-row files (#934): a change adds a fragment, and
`make changes-index` renders `CHANGES.md` from *all* fragments. Nothing enforced the invariant that
every rendered row still has a fragment behind it, so two defects could merge:
- a hand-written aggregate row (a row with no fragment), and
- a **union-merge duplicate** — two copies of the same row, which no existing gate catches
  (`check_docs` links note<->fragment both ways; `changes_index.check()` reads only the fragments).

Why this is a TREE-CONSISTENCY check, not a diff check: a rule that reds "a PR touching CHANGES.md"
would red every open PR, because every lane runs `make changes-index` and a regen legitimately
rewrites the file (measured: six of six open PRs carried a `CHANGES.md` diff). Comparing the row set
against the fragment set on disk passes a legitimate regen by construction, with no cut-off sha and
no base ref — identical behaviour in `ci-unit`, `issue-bot-gates`, and a direct run.

This file pins the contract behaviourally over real `CHANGES.md`/`docs/changes.d/` trees in
`tmp_path` — never source text.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import check_pr_hygiene  # noqa: E402  (the module under test)

#: A well-formed row as `CHANGES.md` renders it (`| date | summary | [note](agent-wiki/<stem>.md) | refs |`).
ROW = ("| 2026-10-30 | {summary} | [{stem}.md](agent-wiki/{stem}.md) | #1063 |\n")
HEADER = "# Changes\n\n| Date | Change | Record | Issue / PR |\n|---|---|---|---|\n"


def _tree(tmp_path: Path, rows: list[str], fragments: list[str]) -> Path:
    """A real tree: `CHANGES.md` holds `rows`; `docs/changes.d/` holds one file per fragment stem."""
    (tmp_path / "CHANGES.md").write_text(HEADER + "".join(rows))
    d = tmp_path / "docs" / "changes.d"
    d.mkdir(parents=True)
    for stem in fragments:
        (d / f"{stem}.md").write_text(ROW.format(summary="x", stem=stem))
    return tmp_path


# --------------------------------------------------------------------------
# positive control: the clean shape passes (249 rows = 249 fragments on main)
# --------------------------------------------------------------------------

def test_every_row_has_a_fragment_passes(tmp_path):
    """The steady state: rows and fragments are 1:1 (on main, 249 = 249)."""
    root = _tree(tmp_path, [ROW.format(summary="a", stem="2026-10-30-a"),
                            ROW.format(summary="b", stem="2026-10-30-b")],
                ["2026-10-30-a", "2026-10-30-b"])
    assert check_pr_hygiene.changes_index_findings(root) == []


def test_real_repo_is_clean():
    """The real checkout satisfies the invariant today (the no-op case, pinned)."""
    assert check_pr_hygiene.changes_index_findings(REPO) == []


# --------------------------------------------------------------------------
# negative controls — one per defect class
# --------------------------------------------------------------------------

def test_hand_added_row_with_no_fragment_fails(tmp_path):
    """A row whose note has no fragment is the #1063 defect — one finding naming stem + remedy."""
    root = _tree(tmp_path, [ROW.format(summary="a", stem="2026-10-30-a"),
                            ROW.format(summary="ghost", stem="2026-10-30-ghost")],
                ["2026-10-30-a"])  # no fragment for 2026-10-30-ghost
    findings = check_pr_hygiene.changes_index_findings(root)
    assert len(findings) == 1
    detail = findings[0]["detail"]
    assert "2026-10-30-ghost" in detail and "docs/changes.d/2026-10-30-ghost.md" in detail, (
        "the finding must name the note AND the fragment path it should have come from")


def test_union_merge_duplicate_row_fails(tmp_path):
    """Two copies of the same row (the union-merge shape) — the condition nothing else catches."""
    dup = ROW.format(summary="a", stem="2026-10-30-a")
    root = _tree(tmp_path, [dup, dup], ["2026-10-30-a"])
    findings = check_pr_hygiene.changes_index_findings(root)
    assert len(findings) == 1, "a duplicated row must produce exactly one finding"
    detail = findings[0]["detail"]
    assert "2026-10-30-a" in detail
    assert "2 rows" in detail and "docs/changes.d/2026-10-30-a.md" in detail


def test_duplicate_is_not_caught_by_fragment_presence_alone(tmp_path):
    """Regression pin for the hole measured on the first draft: both copies DO have a fragment,
    so only the multiplicity condition catches the duplicate."""
    row = ROW.format(summary="a", stem="2026-10-30-a")
    root = _tree(tmp_path, [row, row], ["2026-10-30-a"])
    findings = check_pr_hygiene.changes_index_findings(root)
    # the fragment exists (condition 1 satisfied for both); the finding is condition 2
    assert findings and "appears in 2 rows" in findings[0]["detail"]


# --------------------------------------------------------------------------
# the policy cases that must NOT red (forward-looking)
# --------------------------------------------------------------------------

def test_fragment_present_but_index_stale_passes(tmp_path):
    """A fragment added while CHANGES.md is not yet re-rendered → PASS (currentness not required)."""
    root = _tree(tmp_path,
                 [ROW.format(summary="a", stem="2026-10-30-a")],            # index has only a
                 ["2026-10-30-a", "2026-10-30-b"])                          # b's fragment exists, unrendered
    assert check_pr_hygiene.changes_index_findings(root) == []


def test_missing_changes_md_is_not_a_crash(tmp_path):
    """No CHANGES.md at all → no findings (nothing to compare), never an exception."""
    (tmp_path / "docs" / "changes.d").mkdir(parents=True)
    assert check_pr_hygiene.changes_index_findings(tmp_path) == []


# --------------------------------------------------------------------------
# wiring: the subcommand is reachable from the gate the two paths run
# --------------------------------------------------------------------------

def test_changes_index_subcommand_is_wired_into_the_gate():
    mk = (REPO / "Makefile").read_text()
    recipe = mk.split("\ncheck-pr-hygiene:", 1)[1].split("\npr-hygiene-report:", 1)[0]
    assert "check_pr_hygiene.py changes-index" in recipe, (
        "the check-pr-hygiene recipe must run the changes-index subcommand "
        "(this is the target both ci-unit and issue-bot-gates call)")
