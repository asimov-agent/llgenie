"""Hermetic tests for arm-state reporting in tick_board.sh and the versioned arming step (issue #2182).

#2182 exists because the tick never armed auto-merge and the board could not tell
\"armed and waiting\" from \"armed and impossible\": of 17 open PRs (measured at
`main@3e2e64fa`) 10 were unarmed, 3 were armed-but-DIRTY (inert), and every one
redded `ci-verdict` so none could merge. Three things have to hold, and each is a
test here:

1. Section B reports arm state only when the `--json` field list carries
   `autoMergeRequest,reviewDecision`. WITHOUT those two fields `gh pr list` and
   `gh pr view` return `null` for every PR — the false-measurement bug that made
   an earlier version print `armed=0` for all 17. So a known-armed fixture must
   report `ARMED`, not `unarmed` (regression for the class, not the day).
2. `armed-but-DIRTY` is classified INERT (`ARM-INERT`) and NEVER counted as
   handled: DIRTY gets no CI run and the merge queue never sees it, so the arm
   can never fulfil. A classifier that labels everything the same passes nothing.
3. The arming step reads `autoMergeRequest` back; the exit code of
   `gh pr merge --auto` is NOT the proof (#964) — it exits 0 and arms nothing
   when the base is not the default branch. And a PR whose head has a live run,
   or that is mid-rebase, is never armed (#2069: green+armed at `cc72588c`,
   rebased, green destroyed, never merged).

The tests drive the REAL script `agents/llgenie-planner/scripts/tick_board.sh`
with PR_LIST_JSON / KANBAN_JSON / MAIN_OVERRIDE fixtures (the repository's
allowance for the external-command seam), and read the versioned prompt for the
step text — no network, no gh, no hermes daemon.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "agents"
    / "llgenie-planner"
    / "scripts"
    / "tick_board.sh"
)
PROMPT = (
    Path(__file__).resolve().parent.parent
    / "agents"
    / "llgenie-planner"
    / "prompts"
    / "llgenie-orchestrator-tick.md"
)

MAIN = "7ffbb6f1"


def _run(pr_json, kanban_json="[]", main=MAIN):
    out = subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "REPO": str(Path(tempfile.mkdtemp())),
            "MAIN_OVERRIDE": main,
            "PR_LIST_JSON": pr_json,
            "KANBAN_JSON": kanban_json,
            "HERMES_BIN": "/bin/true",
        },
        timeout=120,
    )
    assert out.returncode == 0, out.stderr
    return out.stdout


def _pr(number, *, armed=False, dirty=False, approved=False, mergeable="MERGEABLE",
        base=MAIN):
    return {
        "number": number,
        "baseRefOid": base,
        "mergeStateStatus": "DIRTY" if dirty else "BLOCKED",
        "mergeable": "CONFLICTING" if dirty else mergeable,
        "headRefOid": f"h{number:07x}",
        "title": f"pr {number}",
        "autoMergeRequest": {"mergeMethod": "SQUASH"} if armed else None,
        "reviewDecision": "APPROVED" if approved else "REVIEW_REQUIRED",
    }


def _fixture(prs, tmp_path):
    pj = tmp_path / "pr.json"
    pj.write_text(json.dumps(prs))
    return str(pj)


def test_a_known_armed_pr_is_reported_armed_not_unarmed(tmp_path):
    """The false-field-list regression: with autoMergeRequest in the fixture and
    in the --json list, a merged-intent PR MUST read ARMED — never unarmed."""
    out = _run(_fixture([_pr(1, armed=True)], tmp_path))
    row = re.search(r"#1\s+\S+\s+\S+\s+(\S+)\s+", out)
    assert row is not None, out
    assert row.group(1) == "ARMED", out
    # a green+approved+unarmed PR must be distinguishable, not swallowed
    assert "unarmed" in out


def test_the_four_states_are_each_reported(tmp_path):
    """armed, unarmed, armed-but-DIRTY (inert), green+approved+unarmed — four
    distinct values the board can act on."""
    prs = [
        _pr(1, armed=True),                       # armed and waiting
        _pr(2),                                   # unarmed, not green
        _pr(3, armed=True, dirty=True),           # armed but DIRTY -> inert
        _pr(4, approved=True, mergeable="MERGEABLE"),  # green+approved+unarmed
    ]
    out = _run(_fixture(prs, tmp_path))
    assert re.search(r"#1\s+\S+\s+\S+\s+ARMED\s", out), out
    assert re.search(r"#2\s+\S+\s+\S+\s+unarmed\s", out), out
    assert re.search(r"#3\s+\S+\s+\S+\s+ARM-INERT\s", out), out
    assert re.search(r"#4\s+\S+\s+\S+\s+green\+appr\+unarm\s", out), out
    # and the ARM summary reflects the same breakdown: "armed" counts every PR
    # carrying a merge request (including the inert one), "inert" is that subset
    # DIRTY reported separately — the issue's own `armed=8 unarmed=10 inert=2`.
    m = re.search(r"ARM\s+armed=(\d+)\s+unarmed=(\d+)\s+armed-but-DIRTY\(inert\)=(\d+)", out)
    assert m is not None, out
    assert (m.group(1), m.group(2), m.group(3)) == ("2", "2", "1"), m.groups()
    # armed(2) counts the two with a request, one of which is inert; the
    # unarmed(2) are #2 and the green+approved #4
    assert "unarmed=2" in out, out


def test_inert_armed_but_dirty_is_never_counted_as_handled(tmp_path):
    """An armed DIRTY PR cannot merge: it is reported impossible (ARM-INERT),
    not as handled. This is the 'a hold whose reason expired is indistinguishable
    from abandonment' failure the issue names."""
    out = _run(_fixture([_pr(1, armed=True, dirty=True)], tmp_path))
    assert "ARM-INERT" in out, out
    # the summary must label the inert one, and the instruction says dispatch a
    # rebase rather than treat it as done
    assert "armed-but-DIRTY(inert)=1" in out, out
    assert "ARM-INERT is NOT handled" in out, out
    assert "llgenie-pr-merge-conflict" in out, out
    # NOT counted as handled: the row label is ARM-INERT, never plain ARMED
    row = re.search(r"#1\s+\S+\s+[^\n]*?ARM-INERT", out)
    assert row is not None, out
    assert not re.search(r"#1\s+\S+\s+[^\n]*?ARMED\s", out), out


def test_unarmed_is_unarmed_whether_blocked_or_fresh(tmp_path):
    """Not-green and not-armer must read unarmed, so the failing check owns it."""
    out = _run(_fixture([_pr(2), _pr(5, dirty=True)], tmp_path))
    assert re.search(r"#2\s+\S+\s+[^\n]*?unarmed", out), out
    assert re.search(r"#5\s+\S+\s+[^\n]*?unarmed", out), out


def test_the_versioned_arming_step_reads_back_and_refuses_live_run_rebase(tmp_path):
    """The versioned prompt (the procedure, not prose) must carry: the
    read-back of autoMergeRequest as the proof (exit code is not), and the
    refuse-to-arm a head with a live run or mid-rebase."""
    text = PROMPT.read_text()
    # the read-back IS the proof (#964: --auto exits 0 and arms nothing off the default branch)
    assert "gh pr view <n> --repo \"$SLUG\" --json autoMergeRequest" in text, text
    assert "exits 0 and arms NOTHING when the base is not the default branch" in text, text
    assert "READ IT BACK" in text or "read it back" in text, text
    # refuse to arm a live run / mid-rebase (#2069)
    assert "live run" in text and "mid-rebase" in text, text
    assert "NEVER arm a PR whose head has a live run" in text or "mid-rebase" in text, text
    # the four states are named in the step
    for state in ("armed", "unarmed", "armed-but-DIRTY", "green+approved+unarmed"):
        assert state in text, (state, text)


def test_the_json_field_list_carries_both_arm_fields():
    """The false-measurement regression this issue exists to prevent: a report
    may only PRINT a field it REQUESTED. `gh pr list`/`gh pr view` return `null`
    silently for a field missing from `--json`, so without
    `autoMergeRequest,reviewDecision` in the list every PR reads `unarmed`.
    The positive fixture above proves the script CLASSIFIES a known-armed PR as
    ARMED; this pins that the live gh invocation asks for the fields its rows
    print, so the request list cannot regress to a null-silent one."""
    text = SCRIPT.read_text()
    assert "autoMergeRequest" in text, text
    assert "reviewDecision" in text, text
    # both must be IN the section-B gh --json list (not merely mentioned in a
    # comment elsewhere in the file): assert the exact joined field list so a
    # regression to a null-silent list (missing either field) is caught.
    assert "title,autoMergeRequest,reviewDecision" in text, text
    # a reviewDecision that vanished from the list while autoMergeRequest stayed
    # is the same class of silent-null regression, so both must sit together
    idx = text.find("--json number,baseRefOid,mergeStateStatus,mergeable,headRefOid,title,autoMergeRequest,reviewDecision")
    assert idx != -1, text
