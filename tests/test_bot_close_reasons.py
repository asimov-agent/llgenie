"""The bot close-reason read (issue #2869): a lane close `not_planned` contradicts its own evidence.

The read walks merged PRs -> closing references -> lane-closed issues -> `state_reason`, and flags
the `not_planned` rows. Only the GitHub API is a stand-in: a `gh` on PATH answering the exact
`gh api` paths the product builds (and 404s everything else), so the test asserts the EXACT reads.
Nothing here mocks or replaces `bot_close_reasons.py` — `merged_pulls`, `claimed_issues` and
`report` are the code under test.

The spec also demands the playbook TEXT: the three lane playbooks must state the close-reason
distinction (`not planned` vs `completed`) and the leave-open rule, or the agent leg keeps choosing
`close` for issues an OPEN PR already implements.

NO-SKIP POLICY: a missing prerequisite is a LOUD FAILURE, never a skip.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
# The ONE import root (issue #796) is `tests/conftest.py`; a test file reaching scripts/ through
# its own `sys.path` entry or a bare import is a NEW root the ratchet refuses. Package form only.
import scripts.bot_close_reasons as bcr  # noqa: E402
from conftest import makefiles_text  # noqa: E402  (the include-resolving Makefile reader)

OWNER = "o"
REPO_NAME = "r"


def _fake_gh(tmp_path: Path, api: dict):
    """`gh` that answers the exact `gh api` paths seeded in `api` and 404s every other path."""
    gh = tmp_path / "gh"
    gh.write_text(f'''#!{sys.executable}
import json, sys
MAP = {repr(api)}
if len(sys.argv) > 2 and sys.argv[1] == "api":
    path = sys.argv[2]
    if path in MAP:
        print(json.dumps(MAP[path]))
    else:
        print(f"gh: Not Found for {{path}} (HTTP 404)", file=sys.stderr)
        sys.exit(1)
else:
    print("[]")
''')
    gh.chmod(0o755)
    return gh


def _pull(n: int, title: str, body: str, merged: bool = True) -> dict:
    return {"number": n, "title": title, "body": body,
            "merged_at": "2026-11-16T20:59:49Z" if merged else None}


def _api() -> dict:
    """The seeded read: 4 merged PRs (1 closed-unmerged), issues in varied closed states."""
    pulls_page1 = [
        _pull(2863, "fix(issue-bot): restate before closing", "closes #2048"),
        _pull(3000, "feat(bot): queue the canonical issue", "**Fix:** ...\n\ncloses #2500\n"),
        _pull(3001, "chore(ops): sweep stale lanes (#2700)", "Part of the sweep. Refs #2700."),
        _pull(3002, "fix(ci): the verdict step", "Issue: #2600\n\ncloses #2800\n"),
        _pull(3003, "docs: touched nothing", "no closing reference here", merged=False),
    ]
    page = "repos/o/r/pulls?state=closed&per_page=100&sort=updated&direction=desc"
    return {
        f"{page}&page=1": pulls_page1,
        f"{page}&page=2": [],
        "repos/o/r/issues/2048": {"number": 2048, "state": "closed",
                                  "state_reason": "completed", "labels": [{"name": "agent:closed"}]},
        "repos/o/r/issues/2500": {"number": 2500, "state": "closed",
                                  "state_reason": "not_planned", "labels": [{"name": "agent:closed"}]},
        # OPEN: the claim has not landed as a close yet — not the read's subject
        "repos/o/r/issues/2600": {"number": 2600, "state": "open",
                                  "state_reason": None, "labels": []},
        # closed without the lane label: the timeline says WHO closed it
        "repos/o/r/issues/2700": {"number": 2700, "state": "closed",
                                  "state_reason": "not_planned", "labels": []},
        "repos/o/r/issues/2700/timeline?per_page=100": [
            {"event": "closed", "actor": {"login": "github-actions[bot]"}}],
        # closed by a human account without the lane label: not the lane's record to audit
        "repos/o/r/issues/2800": {"number": 2800, "state": "closed",
                                  "state_reason": "not_planned", "labels": []},
        "repos/o/r/issues/2800/timeline?per_page=100": [
            {"event": "closed", "actor": {"login": "andyholst"}}],
    }


def test_merged_pulls_pages_until_the_pages_run_out(tmp_path):
    gh = _fake_gh(tmp_path, _api())
    pulls = bcr.merged_pulls(str(gh), f"{OWNER}/{REPO_NAME}", pages=10)
    numbers = [p["number"] for p in pulls]
    assert numbers == [2863, 3000, 3001, 3002], numbers
    assert 3003 not in numbers, "a closed-but-unmerged pull request is not merged work"


def test_claimed_issues_uses_the_gates_own_closing_grammar():
    """Keyword-adjacent closes, `Issue: #N` lines and `(#N)` titles claim; negations do not."""
    pulls = [
        _pull(2863, "fix: a", "closes #2048"),
        _pull(3001, "chore: sweep (#2700)", "Refs #2700."),          # title subject claim only
        _pull(3002, "fix: b", "Issue: #2600\n\ncloses #2800"),
        _pull(3004, "docs: scope note", "This does not close #2900 because it needs its own issue."),
        _pull(3005, "docs: bare ref", "see #3100 for context"),      # a bare #N is not a close
    ]
    claimed = bcr.claimed_issues(pulls)
    assert sorted(claimed) == [2048, 2600, 2700, 2800], sorted(claimed)
    assert 2900 not in claimed and 3100 not in claimed


def test_report_rows_flag_the_not_planned_closure_a_merged_pr_contradicts(tmp_path, capsys):
    gh = _fake_gh(tmp_path, _api())
    rc = bcr.report(f"{OWNER}/{REPO_NAME}", gh=str(gh))
    out = capsys.readouterr().out
    assert rc == 0
    first = out.splitlines()[0]
    assert "merged_prs_read=4" in first and "issues_claimed=5" in first
    assert "bot_closed_rows=3" in first and "flagged=2" in first
    # the lane-closed rows: label-identified (2048, 2500) and timeline-identified (2700)
    assert "#2048 state_reason=completed" in out
    assert "#2500 state_reason=not_planned" in out
    assert "#2700 state_reason=not_planned" in out and "closed-by:github-actions[bot]" in out
    # the contradictions are named where a reader will act on them
    flag_lines = [line for line in out.splitlines() if "FLAG" in line]
    assert len(flag_lines) == 2 and any("#2500" in line for line in flag_lines) \
        and any("#2700" in line for line in flag_lines), out
    # an open issue and a human-closed issue are never rows
    assert "#2600 " not in out and "#2800 " not in out


def test_a_stream_that_cannot_be_read_exits_loud_not_empty(tmp_path):
    gh = _fake_gh(tmp_path, {})  # every read 404s: even the first PR page cannot be read
    with pytest.raises(SystemExit) as caught:
        bcr.report(f"{OWNER}/{REPO_NAME}", gh=str(gh))
    assert "cannot read" in str(caught.value)


def test_report_target_is_wired_in_the_makefile():
    text = makefiles_text(REPO)
    assert "bot-close-reasons-report" in text
    assert "scripts/bot_close_reasons.py report" in text


def test_package_layers_registers_the_module_and_its_single_edge():
    layers = json.loads((REPO / "scripts" / "package-layers.json").read_text())
    registered = any("bot_close_reasons" in members for members in layers["groups"].values())
    assert registered, "bot_close_reasons must live in a layer group"
    edges = {(e["from"], e["to"]) for e in layers["allowed_edges"]}
    assert ("bot_close_reasons", "check_pr_closing") in edges
    assert ("issue_implementer", "check_pr_closing") in edges


# ---- the playbook text the spec holds to the rules (issue #2869) ----

#: lane playbook -> (close-reason distinction, leave-open rule) the text must carry.
PLAYBOOKS = {
    ".hermes/skills/issue-triage/SKILL.md": ("TRIAGE: hold", "not planned", "completed"),
    "agents/llgenie-planner/skills/github-issue-triage/SKILL.md":
        ("implemented (PR OPEN)", "not_planned", "completed"),
    "agents/llgenie-issse-implementer/skills/software-development/llgenie-issue-to-pr/"
    "references/planner-stale-state.md": ("the issue stays open", "not planned", "completed"),
}


def test_the_three_lane_playbooks_state_the_close_reason_split_and_hold():
    for rel, required in PLAYBOOKS.items():
        text = (REPO / rel).read_text()
        for token in required:
            assert token in text, f"{rel} must carry {token!r} (issue #2869)"
