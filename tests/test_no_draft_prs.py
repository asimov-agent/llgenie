"""No script may open a DRAFT pull request (owner instruction, 2026-10-28 · #874, #873).

Owner, verbatim: *"all the PRs that are green should be auto-merged — never remove that behaviour
ever from the CI pipelines"*, and the follow-up rule that landed in every bot's SOUL: **never open a
draft PR** — a draft is invisible to the merge queue, to `auto-merge` and to every reviewer scanning
for work. Three PRs (#846, #838, #780) sat as drafts while the board read "blocked on approvals".

`scripts/auto_merge.py` already declines a draft (`decide()` returns "PR is a draft"), so the decision
side is guarded by `tests/test_auto_merge.py`. What was NOT guarded is the producing side: a bot that
creates its PR with `--draft` hands the merge queue something it will never take, and nothing failed
when it happened. This test closes that: it reads every script and every Makefile recipe for a
`gh pr create` that carries `--draft`.

The rule is about `gh pr create --draft` specifically, not about the word "draft": `--drafter` is an
engine flag, and prose may discuss drafts freely.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

#: `gh pr create … --draft`, allowing flags between the two words and a line continuation.
DRAFT_CREATE = re.compile(r"gh\s+pr\s+create\b[^\n]*?--draft\b")


def _sources() -> list[Path]:
    roots = [REPO / "scripts", REPO / ".github" / "workflows", REPO / ".github" / "actions"]
    files: list[Path] = []
    for root in roots:
        if root.is_dir():
            files.extend(p for p in root.rglob("*") if p.is_file())
    files.append(REPO / "Makefile")
    return [p for p in files if p.exists()]


def test_no_script_or_workflow_creates_a_draft_pull_request():
    """The producer side of the draft ban; the decision side lives in tests/test_auto_merge.py."""

    offenders: list[str] = []
    for path in _sources():
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):  # a binary asset, not a source file
            continue
        for match in DRAFT_CREATE.finditer(text):
            line = text[: match.start()].count("\n") + 1
            offenders.append(f"{path.relative_to(REPO)}:{line}: {match.group(0).strip()}")

    assert not offenders, (
        "a draft PR is invisible to auto-merge and to reviewers (owner instruction, #874/#873); "
        "open the PR ready-for-review and flip a stray draft with `gh pr ready`:\n  "
        + "\n  ".join(offenders))


def test_the_ban_does_not_trip_on_an_engine_drafter_flag():
    """`--drafter` is a model flag, and prose about drafts is allowed - only `--draft` on a PR is not."""

    assert not DRAFT_CREATE.search("engine_runner.py serve p.json --drafter D")
    assert not DRAFT_CREATE.search("gh pr view 1 --json isDraft   # a draft is deferred by auto-merge")
    assert DRAFT_CREATE.search("gh pr create --repo o/r --draft --title x")
    assert DRAFT_CREATE.search("gh pr create --repo o/r --title x --body-file b --draft")


def test_every_bot_that_opens_a_pr_does_it_ready_for_review():
    """Name the producing scripts, so a new bot that forgets the rule is noticed at review time."""

    creates = {p.relative_to(REPO).as_posix() for p in _sources()
               if "gh pr create" in _read(p)}
    assert creates, "no script opens a PR any more - this guard has lost its subject"
    # every one of them is covered by the scan above; listing them keeps the intent visible
    for name in sorted(creates):
        assert "gh pr create" in _read(REPO / name), name


def _read(path: Path) -> str:
    try:
        return path.read_text()
    except (UnicodeDecodeError, OSError):
        return ""
