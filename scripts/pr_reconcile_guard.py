#!/usr/bin/env python3
"""The reconcile guard: read `pulls/<n>` state BEFORE any reconcile action (issue #1749).

Board phantoms are the #1749 class: a lane is handed a PR-numbered red — a head sha, a failing
guard job, a "pending amend" — by a post-merge straggler run or a state-blind board search, and
the PR it names already merged. Measured 2026-11-05: a lane described "open #1742 at head
8482c24b, failing guard job 126996060863, pending amend" while #1742 had merged at 02:33:51Z
(squash `ebabd9f1`, branch deleted, its run 41951437719 all-green, zero amend/guard comments);
another lane re-claimed closed #1644 after merged PR #1743 landed its content. The repo's CI-side
readers are already merged-aware (`ci_verdict.merged_pr_run`, `resolve_run_pr.landed_pr_for_head`,
issue #897); what was missing is the lane-side read: every script scanner filters `state=open`
already, but a lane woken with only a run/branch, or reading a `--state all`/search-form board
row, had no single instrument that answers "is this PR still reconcilable?" before it acts.

This script IS that instrument. It asks `pulls/<n>` exactly one question — `state`, `merged`,
`mergedAt`, `mergeCommitSha`, `headRefOid`, `headRefName`, `mergeable`, `mergeStateStatus` — and
answers with ONE verdict line:

    #<n> merged, read-only (mergeCommit <sha>, merged <ts>, head <oid>, branch <name>)
    #<n> closed, read-only (closed <ts>, head <oid>, branch <name>)
    #<n> open, actionable (head <oid>, mergeState=<S>, mergeable=<M>, branch <name>)

`read-only` is the whole point: a merged/closed verdict forbids the rebase/amend/re-push/body-edit
a phantom would otherwise commission (push-to-deleted-branch and body-edit on a merged PR were the
real risk in #1749). `actionable` names the merge state so the lane reconciles the PR it actually
has, not the head its wake-up carried — a cited head that is not `headRefOid` is the misattributed
claim case (`verifying-planner-claims.md`): the verdict prints both so the mismatch is visible.

A failed read is NOT a verdict: bad number, 404, or API error exits 1 with no verdict line, so an
unevidenced reconcile stays blocked (the same "nothing measuring is loud" rule as #897).

Command (stdlib only, the GitHub API only through a `gh` on PATH):

    guard --pr N [--repo owner/name] [--gh gh]

The repo defaults to `asimov-agent/llgenie` (the `worktree_report.DEFAULT_REPO` convention);
lanes call it through `make lane-reconcile-guard PR=<n>`.
"""
from __future__ import annotations

import argparse
import json
import sys

try:  # the subprocess policy seam (issue #797)
    from .proc import run_ok  # type: ignore
except ImportError:  # pragma: no cover - script mode
    from proc import run_ok  # type: ignore

DEFAULT_REPO = "asimov-agent/llgenie"

#: The fields the verdict is built from — the state triple (#1749) plus the head/merge fields a
#: reconcile claim names. `--jq`-free: `gh pr view --json` prints one JSON object, parsed below
#: rather than regex-scraped. NOTE the shape (measured, gh 2.104.0): `gh pr view` has no REST
#: `merged` boolean — it normalizes `state` to OPEN/CLOSED/MERGED and prints `mergeCommit` as an
#: object (or null); merged is read from the state word plus a non-null `mergedAt`.
_FIELDS = ("state,mergedAt,closedAt,mergeCommit,headRefOid,headRefName,"
           "mergeable,mergeStateStatus")

#: Verdict states this guard knows. Anything else (an API field rename) is a failed read, not a
#: silently different verdict — the row must be understood or the reconcile is blocked.
_KNOWN_STATES = ("OPEN", "CLOSED", "MERGED")

#: `gh pr view --json mergeable` answers MERGEABLE / CONFLICTING / UNKNOWN, not a boolean.
_MERGEABLE_WORDS = {"MERGEABLE": "true", "CONFLICTING": "false", "UNKNOWN": "unknown"}


def _view(gh: str, repo: str, pr: int) -> dict | None:
    """The PR's live view object, or None when `gh` has no answer (404, bad number, API error).

    A non-JSON answer (an error body, a `gh` complaint) is the same no-answer: the guard prints no
    verdict rather than guess one.
    """
    done = run_ok([gh, "pr", "view", str(pr), "--repo", repo, "--json", _FIELDS])
    if done.returncode != 0:
        return None
    try:
        obj = json.loads(done.stdout)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(obj, dict) or str(obj.get("state") or "").upper() not in _KNOWN_STATES:
        return None
    return obj


def _commit_oid(merge_commit) -> str:
    """`mergeCommit` is an object (`{"oid": …}`) or null in `gh pr view` — never a bare sha."""
    if isinstance(merge_commit, dict):
        return str(merge_commit.get("oid") or "")
    return str(merge_commit or "")


def verdict(repo: str, pr: int, gh: str = "gh") -> str | None:
    """The one-line verdict for PR <pr>, or None when the live read failed."""
    obj = _view(gh, repo, pr)
    if obj is None:
        return None
    state = str(obj["state"]).upper()
    merged = state == "MERGED" or bool(obj.get("mergedAt"))
    head = str(obj.get("headRefOid") or "")[:10]
    branch = obj.get("headRefName") or "?"
    if state == "OPEN":
        mergeable = _MERGEABLE_WORDS.get(str(obj.get("mergeable") or "UNKNOWN").upper(), "unknown")
        merge_state = str(obj.get("mergeStateStatus") or "UNKNOWN").upper()
        return (f"#{pr} open, actionable (head {head}, "
                f"mergeState={merge_state}, mergeable={mergeable}, branch {branch})")
    if merged:
        commit = _commit_oid(obj.get("mergeCommit"))[:10] or "?"
        return (f"#{pr} merged, read-only (mergeCommit {commit}, "
                f"merged {obj.get('mergedAt') or '?'}, head {head}, branch {branch})")
    return (f"#{pr} closed, read-only (closed {obj.get('closedAt') or obj.get('mergedAt') or '?'}, "
            f"head {head}, branch {branch})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read pulls/<n> state before any reconcile action (issue #1749).")
    parser.add_argument("--pr", required=True, type=int, help="the PR number the red names")
    parser.add_argument("--repo", default=DEFAULT_REPO,
                        help=f"owner/name gh reads (default {DEFAULT_REPO})")
    parser.add_argument("--gh", default="gh", help="the gh binary to call (default: gh from PATH)")
    args = parser.parse_args(argv)
    line = verdict(args.repo, args.pr, args.gh)
    if line is None:
        print(f"[lane-reconcile-guard] no verdict: pulls/{args.pr} unreadable at {args.repo} — "
              "an unevidenced reconcile stays blocked", file=sys.stderr)
        return 1
    print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
