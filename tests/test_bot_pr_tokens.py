#!/usr/bin/env python3
"""Each bot write runs with the token that can perform it (issue #430).

`make issue-bot-open-pr` ran with `GH_TOKEN: ${{ secrets.BUMP_TOKEN }}` and did two different writes:
post the claim comment (needs `issues: write`) and create the PR (needs the PAT, so CI runs on it).
The PAT carries no Issues write, so run 39513850754 created PR #424 and then died:

    [issue-implementer] gh issue comment 407 … failed (1): GraphQL: Resource not accessible by
    personal access token (addComment)

The job went red after the side effect, the `pr-open` marker was never posted, and the issue looked
unclaimed. These cases run a REAL fake `gh` binary so `_gh()`'s per-call environment is what is
measured — not a monkeypatched stand-in:

* the comment, the PR and the done marker each run with the token for their own write;
* a denied comment fails BEFORE the PR is created, so a red run means nothing was half-done;
* the workflow hands the step both tokens.

NO-SKIP POLICY: every case spawns the real process; none is skipped.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
from scripts import issue_implementer as ii

JOB_TOKEN = "token-for-the-comments-0123456789"
PAT_TOKEN = "token-for-the-pull-request-9876543210"


def _fake_gh(tmp_path: Path, deny=()) -> Path:
    """A `gh` that records `{argv, token}` per call and answers `pr create` with a URL.

    `deny` names an argv prefix (e.g. `["issue", "comment"]`) the fake refuses, the way a token with
    no `issues: write` scope refuses it.
    """
    log = tmp_path / "gh.log"
    gh = tmp_path / "gh"
    gh.write_text(f'''#!{sys.executable}
import json, os, sys
args = sys.argv[1:]
with open({str(log)!r}, "a") as fh:
    fh.write(json.dumps({{"argv": args, "token": os.environ.get("GH_TOKEN")}}) + "\\n")
deny = {list(deny)!r}
for prefix in deny:
    if args[:len(prefix)] == prefix:
        sys.stderr.write("GraphQL: Resource not accessible by personal access token (addComment)\\n")
        sys.exit(1)
if args[:2] == ["pr", "create"]:
    print("https://github.com/acme/llgenie/pull/99")
''')
    gh.chmod(0o755)
    return gh


def _calls(log: Path) -> list[dict]:
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


def _body_file(tmp_path: Path) -> Path:
    """The run's `pr-body.md`: the four AGENTS.md parts, with the issue named (issue #429)."""
    path = tmp_path / ii.PR_BODY_FILE
    path.write_text("Issue: #11 — x\n\nFix: y\n\nBenefit: z\n\nTechnical: scripts/x.py\n")
    return path


def test_every_write_uses_the_token_that_can_perform_it(monkeypatch, tmp_path):
    """Comment -> PR -> done marker, each with its own token, in that order."""

    # Given a job token for the comments and a PAT for the PR
    monkeypatch.setenv("GH_TOKEN", JOB_TOKEN)
    monkeypatch.setenv("PR_TOKEN", PAT_TOKEN)
    gh = _fake_gh(tmp_path)

    # When  the PR is opened
    url = ii.open_pr(str(gh), "acme/llgenie", 11, "agent/issue-11-s", "Fix",
                     str(_body_file(tmp_path)))

    # Then  the comment and the marker carry the job token and the PR carries the PAT
    calls = _calls(tmp_path / "gh.log")
    assert url.endswith("/pull/99"), url
    kinds = [c["argv"][:2] for c in calls]
    assert kinds == [["issue", "comment"], ["pr", "create"], ["issue", "comment"]], kinds
    assert calls[0]["token"] == JOB_TOKEN, calls[0]
    assert calls[1]["token"] == PAT_TOKEN, calls[1]
    assert calls[2]["token"] == JOB_TOKEN, calls[2]
    assert "bot-done: implementer" in " ".join(calls[2]["argv"])


def test_a_denied_comment_costs_no_pr(monkeypatch, tmp_path):
    """The comment runs first: a token that cannot comment never leaves a PR behind."""

    # Given a token that can open a PR but cannot comment
    monkeypatch.setenv("GH_TOKEN", JOB_TOKEN)
    monkeypatch.setenv("PR_TOKEN", PAT_TOKEN)
    gh = _fake_gh(tmp_path, deny=[["issue", "comment"]])

    # When  the PR is opened
    with pytest.raises(SystemExit) as failed:
        ii.open_pr(str(gh), "acme/llgenie", 11, "agent/issue-11-s", "Fix",
                   str(_body_file(tmp_path)))

    # Then  it fails naming the denied write, and no PR was created at all
    assert "addComment" in str(failed.value), failed.value
    kinds = [c["argv"][:2] for c in _calls(tmp_path / "gh.log")]
    assert ["pr", "create"] not in kinds, kinds


def test_without_a_pat_the_legs_own_token_opens_the_pr(monkeypatch, tmp_path):
    """An unset PR_TOKEN falls back to the leg's token rather than failing on an empty env."""

    # Given no PAT in the environment
    monkeypatch.setenv("GH_TOKEN", JOB_TOKEN)
    monkeypatch.delenv("PR_TOKEN", raising=False)
    gh = _fake_gh(tmp_path)

    # When  the PR is opened
    ii.open_pr(str(gh), "acme/llgenie", 11, "agent/issue-11-s", "Fix",
               str(_body_file(tmp_path)))

    # Then  the PR is created with the leg's own token
    creates = [c for c in _calls(tmp_path / "gh.log") if c["argv"][:2] == ["pr", "create"]]
    assert creates and creates[0]["token"] == JOB_TOKEN, creates


def test_the_workflow_hands_the_step_both_tokens():
    """The step that does both writes receives the issues-scoped token AND the PAT."""

    # Given the issue-bot workflow's PR step
    workflow = (REPO / ".github" / "workflows" / "issue-bot.yml").read_text()
    step = workflow.split("- name: Open the PR", 1)[1].split("- name: Report the outcome", 1)[0]

    # When  its env is read
    # Then  the comment token is the job's and the PR token is the PAT
    assert "GH_TOKEN: ${{ github.token }}" in step, step
    assert "PR_TOKEN: ${{ secrets.BUMP_TOKEN }}" in step, step
