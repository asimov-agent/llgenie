"""The issue-close-backfill read (issue #2869): the lane that closed an issue as `not_planned`
while an OPEN PR implemented it learned to hold instead; a READ now names any bot-closed
`not_planned` issue a merged PR closes, so the reason can be corrected to `completed`.

Business logic runs for real — only the GitHub API is a stand-in: a `gh` on PATH that records
its argv and answers `pr list` / `issue view`, so the test asserts the EXACT request the product
builds. Nothing mocks or replaces `issue_close_backfill.read`.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import issue_close_backfill as icb  # noqa: E402

OWNER = "asimov-agent"
REPO_NAME = "llgenie"


def _fake_gh(tmp_path: Path, opts: dict):
    """`gh` that records every argv as ONE JSON line and answers the product's queries.

    opts:
      merged_prs: [{number,title,mergedAt,closingIssuesReferences,baseRefName}]
      issues:       {num: {"state","stateReason","labels","closedBy"}}
    """
    tmp_path.mkdir(parents=True, exist_ok=True)
    log = tmp_path / "gh.log"
    merged = opts.get("merged_prs", [])
    issues = opts.get("issues", {})

    gh = tmp_path / "gh"
    gh.write_text(f'''#!{sys.executable}
import json, sys, pathlib
args = sys.argv[1:]
MERGED = {json.dumps(merged)}
ISSUES = {json.dumps(issues)}
with open({str(log)!r}, "a") as fh:
    fh.write(json.dumps(args) + "\\n")
if args[:2] == ["pr", "list"]:
    print(json.dumps(MERGED))
elif args[:2] == ["issue", "view"]:
    n = args[2]
    if n not in ISSUES:
        print("not found", file=sys.stderr); sys.exit(1)
    print(json.dumps(ISSUES[n]))
else:
    print("[]")
''')
    gh.chmod(0o755)
    return gh, log


def _calls(log: Path) -> list[list[str]]:
    return [json.loads(ln) for ln in log.read_text().splitlines() if ln.strip()]


def _pr(number, title, merged_at="2026-11-16T20:00:00Z", closes=None, base="main"):
    return {"number": number, "title": title, "mergedAt": merged_at,
            "closingIssuesReferences": [{"number": n} for n in (closes or [])],
            "baseRefName": base}


def _issue(num, state="CLOSED", reason="not_planned", bot_closed=True):
    return {"state": state, "stateReason": reason,
            "labels": [{"name": "agent:closed"}] if bot_closed else [],
            "closedBy": {"login": "github-actions[bot]" if bot_closed else "andyholst"}}


def _issue_open(num):
    # JSON-safe (the fake gh embeds these as a Python literal): no `null` tokens.
    return {"state": "OPEN", "stateReason": "", "labels": [], "closedBy": {}}


def test_backfill_names_a_bot_closed_not_planned_issue_a_merged_pr_closes(tmp_path):
    """The read's whole point: #2048-type issues — closed not_planned, then a merged PR closes it."""

    # Given a merged PR whose body GitHub parsed as closing #2048, and #2048 closed not_planned
    gh, log = _fake_gh(tmp_path, {
        "merged_prs": [_pr(2863, "test(pick): offer-or-skip coverage", closes=[2048])],
        "issues": {"2048": _issue(2048, reason="not_planned")},
    })

    # When  the backfill is read
    matches = icb.read(REPO_NAME, gh=str(gh))

    # Then  it names #2048 as needing a `completed` correction, attributed to merged PR #2863
    assert len(matches) == 1
    m = matches[0]
    assert m["issue"] == 2048 and m["pr"] == 2863
    assert m["needs_correction"] is True and m["state_reason"] == "not_planned"


def test_backfill_labels_an_already_corrected_issue_completed(tmp_path):
    """#2048's reason was hand-corrected to `completed`; the read records that as corrected."""

    # Given #2048 now carries the corrected `completed` reason
    gh, log = _fake_gh(tmp_path, {
        "merged_prs": [_pr(2863, "test(pick): coverage", closes=[2048])],
        "issues": {"2048": _issue(2048, reason="completed")},
    })

    # When  the backfill is read
    matches = icb.read(REPO_NAME, gh=str(gh))

    # Then  it still names #2048 (a merged PR closes it) but reports it corrected, not flagged
    assert len(matches) == 1
    assert matches[0]["issue"] == 2048
    assert matches[0]["state_reason"] == "completed" and matches[0]["needs_correction"] is False


def test_backfill_skips_a_human_closed_issue_and_an_open_or_pr_is_ignored(tmp_path):
    """Only a BOT-closed, CLOSED issue a merged PR closes is a match — others are left alone."""

    # Given a merged PR closes three issues: a human-closed one, a bot-open one, and one still open
    gh, log = _fake_gh(tmp_path, {
        "merged_prs": [_pr(10, "implements several", closes=[1, 2, 3])],
        "issues": {
            "1": _issue(1, reason="not_planned", bot_closed=False),   # human closed it
            "2": _issue(2, reason="not_planned"),                     # bot closed it, but...
            "3": _issue_open(3),                # still open, not a match
        },
    })

    # When  the backfill is read with those merged PRs (2 is the only bot-closed closed one)
    matches = icb.read(REPO_NAME, gh=str(gh))

    # Then  only #2 is a match — the human's close and the still-open issue are not the bot's read
    assert [m["issue"] for m in matches] == [2]


def test_backfill_reads_every_closing_reference_of_a_pr(tmp_path):
    """A merged PR that closes several issues surfaces each one, not just the first."""

    # Given one merged PR whose body closes #2048 and #2050, both bot-closed not_planned
    gh, log = _fake_gh(tmp_path, {
        "merged_prs": [_pr(2863, "coverage", closes=[2048, 2050])],
        "issues": {"2048": _issue(2048), "2050": _issue(2050)},
    })

    # When  the backfill is read
    matches = icb.read(REPO_NAME, gh=str(gh))

    # Then  both issues are named
    assert sorted(m["issue"] for m in matches) == [2048, 2050]


def test_backfill_read_exits_zero_with_no_matches_and_nothing_to_correct(tmp_path, capsys):
    """The read is a report, never a red run: a clean board prints a line and exits 0."""

    # Given no merged PR carries a closing reference
    gh, log = _fake_gh(tmp_path, {"merged_prs": [], "issues": {}})

    # When  the read command runs
    rc = icb.main(["read", "--repo", REPO_NAME, "--gh", str(gh)])

    # Then  it names nothing and exits 0
    assert rc == 0
    assert "no bot-closed issue" in capsys.readouterr().out


def test_backfill_main_flags_a_correction_and_exits_zero(tmp_path, capsys):
    """The report prints the correction line for a not_planned match but never fails the run."""

    # Given a bot-closed not_planned issue a merged PR closes
    gh, log = _fake_gh(tmp_path, {
        "merged_prs": [_pr(2863, "coverage", closes=[2048])],
        "issues": {"2048": _issue(2048, reason="not_planned")},
    })

    # When  the read command runs
    rc = icb.main(["read", "--repo", REPO_NAME, "--gh", str(gh)])

    # Then  it names the correction and still exits 0 (a read never fails because the board is wrong)
    out = capsys.readouterr().out
    assert "NEEDS-CORRECTION" in out
    assert "correct #2048" in out
    assert rc == 0
