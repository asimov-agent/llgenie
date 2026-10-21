#!/usr/bin/env python3
"""Merge a PR only when this run is green and the PR is conflict-free (issue #482).

The policy: a same-repo, non-draft pull request whose pipeline is green AND whose merge state is CLEAN is
squash-merged by CI, without waiting for a human. Everything else is DEFERRED — printed and exited 0,
never failed — because "not green-and-clean" is a decision for a person, not a broken run:

  * `state != OPEN`        — already merged or closed
  * `isDraft`              — the author is still working
  * `mergeable != MERGEABLE`      — GitHub has not computed it yet, or there are conflicts
  * `mergeStateStatus != CLEAN`   — DIRTY (conflicts), BEHIND (needs an update), BLOCKED (checks/reviews)
  * the head moved since this run started (`headRefOid != the run's sha`) — the newer run decides
  * the `do-not-merge` label      — the human hold

The merge itself is `gh pr merge --squash --delete-branch --match-head-commit <sha>`, run with the OWNER
PAT by the caller: a merge made with the job's own token starts no workflows, so the post-merge run on
`main` would never happen. Afterwards the closing references are verified (`scripts/verify_closure.py`),
so a `closes #n` that did not bind is a red run instead of an issue left open.

Commands (stdlib only, the GitHub API only through a `gh` on PATH):
  auto-merge --repo R --pr N --head-sha S [--dry] [--gh gh]
"""
from __future__ import annotations

import argparse
import json
import subprocess

import verify_closure

REQUIRED_STATE = "OPEN"
REQUIRED_MERGEABLE = "MERGEABLE"
REQUIRED_MERGE_STATE = "CLEAN"
HOLD_LABEL = "do-not-merge"


def _gh(gh: str, args: list[str]) -> str:
    r = subprocess.run([gh, *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"[auto-merge] {gh} {' '.join(args)} failed ({r.returncode}): {r.stderr.strip()}")
    return r.stdout


def pr_state(gh: str, repo: str, pr: int) -> dict:
    """What GitHub says about this PR right now: the merge decision is read from here, in one call."""
    out = _gh(gh, ["pr", "view", str(pr), "--repo", repo, "--json",
                   "state,isDraft,mergeable,mergeStateStatus,headRefOid,labels,headRepository"])
    return json.loads(out or "{}")


def decide(state: dict, head_sha: str, hold_label: str = HOLD_LABEL) -> "str | None":
    """None when the PR may be merged; otherwise the reason it is deferred to a human."""
    labels = {str(l.get("name")) for l in (state.get("labels") or [])}
    if hold_label in labels:
        return f"the `{hold_label}` label is set (the human hold)"
    if (state.get("state") or "").upper() != REQUIRED_STATE:
        return f"PR is {state.get('state')}"
    if state.get("isDraft"):
        return "PR is a draft"
    if (state.get("mergeable") or "").upper() != REQUIRED_MERGEABLE:
        return (f"mergeable is {state.get('mergeable')} (conflicts, or GitHub has not finished "
                f"computing it)")
    status = (state.get("mergeStateStatus") or "").upper()
    if status != REQUIRED_MERGE_STATE:
        why = {"DIRTY": "conflicts with main", "BEHIND": "behind main (needs an update)",
               "BLOCKED": "blocked by a required check or review"}.get(status, "not mergeable yet")
        return f"mergeStateStatus is {status or 'UNKNOWN'} ({why})"
    if head_sha and (state.get("headRefOid") or "") != head_sha:
        return (f"the head moved since this run started "
                f"({(state.get('headRefOid') or '')[:8]} != {head_sha[:8]}); the newer run decides")
    return None


def merge(gh: str, repo: str, pr: int, head_sha: str, delete_branch: bool = True) -> str:
    """Squash-merge exactly the validated commit; delete the branch only when it is in THIS repo.

    A head in the owner's fork (issue #488) is a normal case here — every agent PR is pushed there — but the
    base token cannot delete a branch in the fork, and asking it to would fail a run whose merge succeeded.
    """
    argv = ["pr", "merge", str(pr), "--repo", repo, "--squash"]
    if delete_branch:
        argv.append("--delete-branch")
    argv += ["--match-head-commit", head_sha]
    return _gh(gh, argv)


def run(gh: str, repo: str, pr: int, head_sha: str, dry: bool = False) -> int:
    state = pr_state(gh, repo, pr)
    fields = ("state", "isDraft", "mergeable", "mergeStateStatus", "headRefOid")
    print(f"[auto-merge] PR #{pr}: " + json.dumps({k: state.get(k) for k in fields}))
    reason = decide(state, head_sha)
    if reason:
        print(f"[auto-merge] PR #{pr} deferred to a human: {reason}")
        return 0
    head_repo = ((state.get("headRepository") or {}).get("nameWithOwner") or "").lower()
    same_repo = not head_repo or head_repo == repo.lower()
    keeps_branch = " (its branch stays in the fork)" if not same_repo else ""
    if dry:
        print(f"[auto-merge] would squash-merge PR #{pr} at {(head_sha or '')[:8]}{keeps_branch}")
        return 0
    print(f"[auto-merge] merging PR #{pr} at {head_sha[:8]} (green + CLEAN){keeps_branch}")
    print(merge(gh, repo, pr, head_sha, delete_branch=same_repo).strip())
    return verify_closure.verify(gh, repo, pr)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="auto_merge", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("auto-merge", help="merge the PR when this run is green and the PR is CLEAN")
    m.add_argument("--repo", required=True)
    m.add_argument("--pr", type=int, required=True)
    m.add_argument("--head-sha", default="", help="the head commit this run validated")
    m.add_argument("--gh", default="gh")
    m.add_argument("--dry", action="store_true", help="print the decision, merge nothing")
    args = p.parse_args(argv)
    return run(args.gh, args.repo, args.pr, args.head_sha, args.dry)


if __name__ == "__main__":
    raise SystemExit(main())
