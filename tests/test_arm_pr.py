#!/usr/bin/env python3
"""Hermetic tests for arm_pr.sh (issue #2182): the tick's arming step.

Covers the four states a PR read can be in (armed / unarmed /
armed-but-DIRTY-inert / green+approved+unarmed) and the #964 defect that the
EXIT CODE is never proof: `gh pr merge --auto` exits 0 while arming NOTHING (e.g.
when the base is not the default branch). The only proof is an autoMergeRequest
read back AFTER the arm, and the script must REFUSE to claim success without one.

The refusal-to-arm-a-live-run case (issue #2069) is exercised via a fake `gh`
whose `pr checks` shows an in-progress row: the arm must not run.

The `gh` command is faked on PATH (never real) exactly as the delegate tests fake
`hermes`. PR state is injected as a single-PR gh --json string via PR_STATE.
"""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "agents"
    / "llgenie-planner"
    / "scripts"
    / "arm_pr.sh"
)


def _pr(armed=False, ms="CLEAN", mergeable="MERGEABLE", review="APPROVED"):
    return {
        "autoMergeRequest": {"enabledAt": "2026-11-08T00:00:00Z"} if armed else None,
        "mergeStateStatus": ms,
        "mergeable": mergeable,
        "reviewDecision": review,
        "headRefOid": "bbbbbbbb" * 4,
        "baseRefOid": "aaaaaaaa" * 4,
    }


class FakeGH:
    """A configurable fake `gh` on a temp PATH."""

    def __init__(self, tmp_path, checks="", merge_rc=0, view_after_arm="armed"):
        self.dir = Path(tmp_path) / "bindir"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.gh = self.dir / "gh"
        # view_after_arm: what `pr view` returns for autoMergeRequest AFTER merge:
        #   "armed"  -> real arm read back (success)
        #   "unarmed" -> armed nothing (#964 shape)
        script = f"""#!/bin/bash
if [ "$1" = "pr" ] && [ "$2" = "checks" ]; then printf %s '{checks}'; exit 0; fi
if [ "$1" = "pr" ] && [ "$2" = "merge" ]; then exit {merge_rc}; fi
if [ "$1" = "pr" ] && [ "$2" = "view" ]; then
  if [ "$VIEW_AFTER" = "unarmed" ]; then printf %s '{{"autoMergeRequest":null}}'
  else printf %s '{{"autoMergeRequest":{{"enabledAt":"2026-11-08T00:00:00Z"}}}}'; fi
  exit 0
fi
exit 0
"""
        self.gh.write_text(script)
        self.gh.chmod(0o755)


def _run(state, view_after_arm="armed", checks="", dry=False):
    tmp = Path(tempfile.mkdtemp())
    fgh = FakeGH(tmp, checks=checks, view_after_arm=view_after_arm)
    env = {
        **os.environ,
        "PATH": f"{fgh.dir}:{os.environ.get('PATH','')}",
        "REPO": str(Path(tempfile.mkdtemp())),
        "SLUG": "asimov-agent/llgenie",
        "PR_STATE": json.dumps(state),
        "VIEW_AFTER": view_after_arm,
        "DRY": "1" if dry else "0",
    }
    out = subprocess.run(
        ["bash", str(SCRIPT), "7"], capture_output=True, text=True, env=env, timeout=60
    )
    return out


def test_armed_pr_is_left_alone(tmp_path):
    out = _run(_pr(armed=True))
    assert out.returncode == 0, out.stderr
    assert "already armed" in out.stdout
    assert "gh pr merge" not in out.stdout  # never run the arm on an armed PR


def test_unarmed_not_green_is_reported_not_armed(tmp_path):
    out = _run(_pr(review="CHANGES_REQUESTED"))
    assert out.returncode == 0
    assert "unarmed and not green" in out.stdout
    assert "gh pr merge" not in out.stdout


def test_armed_but_dirty_is_inert_and_routed(tmp_path):
    # An armed DIRTY PR is impossible — routed to the rebase lane, never counted
    # as handled, and never re-armed.
    out = _run(_pr(armed=True, ms="DIRTY", mergeable="CONFLICTING"))
    assert out.returncode == 0
    assert "ARMED-BUT-DIRTY" in out.stdout
    assert "llgenie-pr-merge-conflict" in out.stdout
    assert "INERT" in out.stdout
    assert "gh pr merge" not in out.stdout  # the arm never runs on an inert PR


def test_green_approved_unarmed_is_armed_and_read_back(tmp_path):
    # The core success path: green + approved + unarmed -> arm, then the arm is
    # PROVEN by an autoMergeRequest read back (the exit code is not proof).
    out = _run(_pr())
    assert out.returncode == 0, out.stdout + out.stderr
    assert "ARMING" in out.stdout
    assert "ARMED #7" in out.stdout
    assert "enabledAt=2026-11-08T00:00:00Z" in out.stdout
    assert "read-back is what counts" in out.stdout


def test_exit_0_but_no_arm_read_back_is_not_success(tmp_path):
    # issue #964 shape: `gh pr merge` exits 0 but automated merge is NOT set
    # (the base was not the default branch). The exit code must not be trusted;
    # the missing autoMergeRequest after the command is a hard failure.
    out = _run(_pr(), view_after_arm="unarmed")
    assert out.returncode == 2, f"expected NON-zero refusal, rc={out.returncode}"
    assert "autoMergeRequest is STILL absent" in out.stdout
    assert "NOT success" in out.stdout


def test_refuses_to_arm_a_live_run(tmp_path):
    # issue #2069: a head with an in-progress/pending check must NOT be armed.
    out = _run(_pr(), checks="pending  just-ran    #7\n")
    assert out.returncode == 1
    assert "REFUSED" in out.stdout
    assert "live run" in out.stdout
    assert "gh pr merge" not in out.stdout


def test_dry_run_classifies_without_running_the_arm(tmp_path):
    out = _run(_pr(), dry=True)
    assert out.returncode == 0
    assert "DRY:" in out.stdout
    assert "gh pr merge 7" in out.stdout
    assert "ARMED #7" not in out.stdout  # nothing actually armed
