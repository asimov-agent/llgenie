#!/usr/bin/env python3
"""A finished PR is armed when it is done, not when it is approved (fleet rule 16, issue #873).

The owner's directive: "their skill behavior should always be to set the PRs to automerge when they are done
with the issue/pr work." The producing lane closes its own work; "armed" is the last move, not a chore for the
merger. A finished but unarmed PR is invisible to every sweep, so the gate exists to make an unarmed finished
PR a named finding rather than a silence.

Queue semantics (issue #2378): the repository's merge lane is the CI `auto-merge` job — it squash-merges a PR
that is GREEN and mergeStateStatus CLEAN (AGENTS.md, "CI merges a green, conflict-free PR; the agent never
merges it by hand"), and the agent lane is forbidden from running `gh pr merge` (no `--auto` either). The old
reading of rule 16 — every mergeable, non-draft, default-based PR must carry `autoMergeRequest` — flagged every
PR whose checks were still running and every PR already inside the auto-merge queue, so the alarm was red on
every scheduled tick while the board was healthy (measured at 2f6574ea8: 4/4 open lanes flagged mid-CI). This
gate now reads the same board the merge lane reads:

- **not finished (skip, not flagged)**: a draft; base != default branch (#964); not mergeable (DIRTY/
  CONFLICTING/UNKNOWN); checks not complete (QUEUED/IN_PROGRESS rows, or no rows yet); checks that finished
  RED (CI already names the failure — a red PR is work in progress, not finished work); an approval chain
  still in flight (reviewDecision REVIEW_REQUIRED or CHANGES_REQUESTED — the lane's verdict chain has not
  landed yet).
- **armed or queued (not a finding)**: `autoMergeRequest != null` (a real GitHub arm, the historical #873
  form); `mergeStateStatus == CLEAN` (green + conflict-free — the CI auto-merge job lands it: that IS the
  queue); an in-flight approval chain (see above — the work is not finished yet).
- **finding (rule 16 holds)**: checks all COMPLETED and all green, mergeable, non-draft, default-based, and
  NEITHER armed NOR in the queue — i.e. green-but-BLOCKED-after-approval (nothing will land it) or
  green-but-BEHIND (stale against main; the auto-merge job refuses BEHIND, so the lane must rebase).

What this gate audits — every OPEN PR, listed in one call, filtered in code (issue #1021's lesson: never let
`gh` narrow the denominator, or the audited set drifts).

`report` prints the findings and exits 0 (the board is readable even when it is dirty); `check` exits 1 when any
finished PR is neither armed nor queued. Use `--repo OWNER/NAME` and `--default-branch` (default `main`) for
forks or release branches.

Usage
  python3 scripts/check_arms.py report                 # every open PR and its state, exit 0
  python3 scripts/check_arms.py check                  # fail (exit 1) on any finished-but-unarmed PR
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

DEFAULT_BRANCH = "main"

#: mergeStateStatus value that means the CI auto-merge job already holds this PR (issue #2378).
CLEAN = "CLEAN"
#: check-rollup conclusions that mean the PR finished RED (work in progress; CI already names it).
RED_CONCLUSIONS = {"FAILURE", "CANCELLED", "TIMED_OUT", "START_FAILURE"}
#: reviewDecision values that mean the verdict chain has not landed — the work is not finished.
OPEN_REVIEW_CHAIN = {"REVIEW_REQUIRED", "CHANGES_REQUESTED"}


def open_prs(repo: str) -> list[dict]:
    """Every open PR with the fields this gate reads — one list call, filtered in code, never a `--label`."""
    listed = subprocess.run(  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
        ["gh", "pr", "list", "--repo", repo, "--state", "open", "--limit", "200",
         "--json",
         "number,title,isDraft,baseRefName,mergeable,autoMergeRequest,mergeStateStatus,reviewDecision,statusCheckRollup"],
        capture_output=True, text=True)
    if listed.returncode != 0:
        raise SystemExit(f"[check-arms] FAIL: cannot list PRs: {listed.stderr.strip()}")
    return json.loads(listed.stdout or "[]")


def checks_verdict(pr: dict) -> str:
    """Classify the PR's check rollup: 'in-ci' (not terminal yet), 'red', or 'green'.

    A row is non-terminal while its status is not COMPLETED and it carries no conclusion; a rollup with no
    rows at all is a PR whose checks have not appeared — also not finished (issue #2378: a mid-CI PR was
    audited as 'finished' purely because `mergeable == MERGEABLE`, which reds the alarm on every board tick).
    """
    rollup = pr.get("statusCheckRollup") or []
    if not rollup:
        return "in-ci"
    pending = 0
    for row in rollup:
        status = (row.get("status") or "").upper()
        conclusion = (row.get("conclusion") or "").upper()
        if status and status != "COMPLETED":
            pending += 1
        elif not status and not conclusion:
            pending += 1
        elif conclusion in RED_CONCLUSIONS:
            return "red"
    return "in-ci" if pending else "green"


def queue_state(pr: dict) -> "str | None":
    """Why this PR is NOT a finding under the merge lane, or None when nothing holds it.

    'armed' is GitHub's own `autoMergeRequest` (the historical #873 form); 'queued' is the CI auto-merge
    job's hold: mergeStateStatus CLEAN means green + conflict-free and the job lands it (AGENTS.md, issue
    #2378); an in-flight review chain means the work is not finished yet, so nothing owes an arm.
    """
    if pr.get("autoMergeRequest") is not None:
        return "armed (autoMergeRequest)"
    if (pr.get("mergeStateStatus") or "") == CLEAN:
        return "queued (mergeStateStatus CLEAN — CI auto-merge job lands it)"
    if (pr.get("reviewDecision") or "") in OPEN_REVIEW_CHAIN:
        return "in-flight (review chain not landed — not finished work)"
    return None


def finished(pr: dict, default_branch: str = DEFAULT_BRANCH) -> bool:
    """True when rule 16 says this open PR owes an arm/queue entry: done, green, mergeable, default-based."""
    if pr.get("isDraft"):
        return False
    if (pr.get("baseRefName") or "") != default_branch:
        return False
    if (pr.get("mergeable") or "") not in ("MERGEABLE", "CLEAN"):
        return False
    return checks_verdict(pr) == "green"


def finished_unarmed(pr: dict, default_branch: str = DEFAULT_BRANCH) -> bool:
    """True when this open PR is finished yet neither armed nor inside the CI auto-merge queue."""
    if not finished(pr, default_branch):
        return False
    return queue_state(pr) is None


def findings(prs: list[dict], default_branch: str = DEFAULT_BRANCH) -> list[dict]:
    out = []
    for pr in prs:
        if finished_unarmed(pr, default_branch):
            out.append({
                "number": pr["number"],
                "title": pr.get("title") or "",
                "base": pr.get("baseRefName") or "",
                "state": pr.get("mergeStateStatus") or "",
            })
    return out


def state_of(pr: dict, default_branch: str = DEFAULT_BRANCH) -> str:
    """One readable state per open PR: why it is armed, why it is not a finding, or why it IS one."""
    if pr.get("isDraft"):
        return "draft (not finished)"
    if (pr.get("baseRefName") or "") != default_branch:
        return "stacked base, #964 (cannot be armed)"
    if (pr.get("mergeable") or "") not in ("MERGEABLE", "CLEAN"):
        return f"not mergeable: {pr.get('mergeable')}"
    checks = checks_verdict(pr)
    if checks == "in-ci":
        return "in CI (checks not terminal — not finished yet, #2378)"
    if checks == "red":
        return "red (CI already names this failure)"
    queue = queue_state(pr)
    if queue:
        return queue
    return (f"FINDING: green, review chain complete, no arm and no queue row "
            f"(mergeStateStatus {pr.get('mergeStateStatus') or '?'})")


def report(prs: list[dict], default_branch: str = DEFAULT_BRANCH) -> str:
    lines = [f"[check-arms] {len(prs)} open PR(s), default branch `{default_branch}`:"]
    covered = 0
    for pr in sorted(prs, key=lambda p: p["number"]):
        state = state_of(pr, default_branch)
        lines.append(f"  #{pr['number']}: {state}")
        if not finished_unarmed(pr, default_branch):
            covered += 1
    lines.append(f"[check-arms] {covered}/{len(prs)} armed, queued, or legitimately unfinished")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "check arms").splitlines()[0])
    parser.add_argument("mode", nargs="?", default="report", choices=("check", "report"))
    parser.add_argument("--repo", default="asimov-agent/llgenie")
    parser.add_argument("--default-branch", default=DEFAULT_BRANCH)
    args = parser.parse_args(argv)

    prs = open_prs(args.repo)
    print(report(prs, args.default_branch))
    if args.mode == "report":
        return 0
    unarmed = findings(prs, args.default_branch)
    if unarmed:
        print("[check-arms] FAIL: finished PR(s) are green yet carry neither an arm nor a queue row "
              "(#873; queue semantics #2378):")
        for pr in unarmed:
            print(f"  #{pr['number']}: {pr['title']} (mergeStateStatus {pr['state'] or '?'})")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
