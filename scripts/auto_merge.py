#!/usr/bin/env python3
"""Merge a PR only when this run is green and the PR is conflict-free (issues #482, #488, #491).

The policy: a non-draft pull request whose pipeline is green AND whose merge state is CLEAN is
squash-merged by CI, without waiting for a human. A head may be this repository or the owner's fork
(`andyholst/llgenie`) — every agent PR is pushed there. Everything else is DEFERRED, never failed:

  * `state != OPEN`        — already merged or closed
  * `isDraft`              — the author is still working
  * `mergeable != MERGEABLE`      — GitHub has not computed it yet, or there are conflicts
  * `mergeStateStatus != CLEAN`   — DIRTY (conflicts), BEHIND (needs an update), BLOCKED
  * the head moved since this run started (`headRefOid != the run's sha`) — the newer run decides
  * the `do-not-merge` label      — the human hold

TWO things make a deferral honest rather than silent (issue #491):

  * a review-blocked GREEN PR may be approved by the OTHER allowed identity and then merged — the state is
    `mergeable: MERGEABLE` + `mergeStateStatus: BLOCKED` + `reviewDecision: REVIEW_REQUIRED`, the workflow's
    own `needs:` gate already proved every needed job succeeded, the author is a different account from the
    merge token's (GitHub refuses a self-approval), and the author is one of this repo's two identities
    (`andyholst`, `asimov-agent`). Any other review-blocked PR waits for a person;
  * every deferral posts ONE comment per head SHA (`<!-- auto-merge: deferred <sha> -->`) carrying the reason
    and what would unblock it, so "why is this not merged?" is answerable from the PR, not from a run log.

The merge itself is `gh pr merge --squash [--delete-branch] --match-head-commit <sha>` with the OWNER PAT by
the caller (a merge with the job's own token starts no workflows), and `--delete-branch` is omitted for a fork
head (the base token cannot delete a branch in the fork). Afterwards `scripts/verify_closure.py` proves the
body's `closes #n` bound.

Commands (stdlib only, the GitHub API only through a `gh` on PATH):
  auto-merge --repo R --pr N --head-sha S [--dry] [--approve-when-review-required] [--gh gh]
  explain    --repo R --pr N [--head-sha S] [--gh gh]      print the verdict, write nothing
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
#: The two identities this repository allows on a PR (AGENTS.md: `Andy Holst`, `Asimov Agent`), as logins.
ALLOWED_AUTHORS = ("andyholst", "asimov-agent")
#: One deferral comment per head SHA — re-posted only when the head moves.
DEFERRAL_MARKER = "<!-- auto-merge: deferred {} -->"


def _gh(gh: str, args: list[str]) -> str:
    r = subprocess.run([gh, *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"[auto-merge] {gh} {' '.join(args)} failed ({r.returncode}): {r.stderr.strip()}")
    return r.stdout


def pr_state(gh: str, repo: str, pr: int) -> dict:
    """What GitHub says about this PR right now: the merge decision is read from here, in one call."""
    out = _gh(gh, ["pr", "view", str(pr), "--repo", repo, "--json",
                   "state,isDraft,mergeable,mergeStateStatus,headRefOid,labels,headRepository,"
                   "author,reviewDecision"])
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


def review_blocked(state: dict) -> bool:
    """True only for the one procedural block a bot may clear: a required review, everything else green."""
    return ((state.get("mergeable") or "").upper() == REQUIRED_MERGEABLE
            and (state.get("mergeStateStatus") or "").upper() == "BLOCKED"
            and (state.get("reviewDecision") or "").upper() == "REVIEW_REQUIRED")


def token_login(gh: str) -> str:
    """The account the merge token belongs to — GitHub refuses a pull request approving its own author."""
    return _gh(gh, ["api", "user", "--jq", ".login"]).strip()


def approve(gh: str, repo: str, pr: int) -> str:
    body = ("Approved by the repo's `auto-merge` job (issue #491): the run is green and the only thing "
            "missing was a required review. It merges immediately if the state becomes CLEAN; "
            "`do-not-merge` holds a PR at any time.")
    return _gh(gh, ["pr", "review", str(pr), "--repo", repo, "--approve", "--body", body])


def try_approve(gh: str, repo: str, pr: int, state: dict, dry: bool = False) -> "str | None":
    """Approve a review-blocked green PR with the other allowed identity; None on success, else the reason."""
    author = ((state.get("author") or {}).get("login") or "").strip()
    me = token_login(gh)
    if author and author.lower() == me.lower():
        return (f"a required review is missing, and the PR's author (`{author}`) is the merge token's own "
                f"account — GitHub refuses a self-approval, so a human must approve it")
    if author.lower() not in ALLOWED_AUTHORS:
        return (f"a required review is missing, and the author `{author or 'unknown'}` is not one of this "
                f"repo's identities ({', '.join(ALLOWED_AUTHORS)}) — a bot does not approve a stranger's PR")
    if dry:
        print(f"[auto-merge] would approve PR #{pr} as `{me}` (a required review is the only blocker)")
        return None
    print(f"[auto-merge] PR #{pr} is green but blocked by a required review — approving as `{me}` "
          f"(authored by `{author}`)")
    print(approve(gh, repo, pr).strip())
    return None


def pr_comments(gh: str, repo: str, pr: int) -> list[str]:
    out = _gh(gh, ["pr", "view", str(pr), "--repo", repo, "--json", "comments"])
    return [str(c.get("body") or "") for c in (json.loads(out or "{}").get("comments") or [])]


def defer(gh: str, repo: str, pr: int, head_sha: str, reason: str, dry: bool = False) -> None:
    """Say why on the PR, once per head SHA: a run log is not where a reviewer looks."""
    print(f"[auto-merge] PR #{pr} deferred to a human: {reason}")
    marker = DEFERRAL_MARKER.format((head_sha or "")[:40])
    if dry:
        print(f"[auto-merge] would comment the deferral on PR #{pr} ({marker})")
        return
    if any(marker in body for body in pr_comments(gh, repo, pr)):
        print(f"[auto-merge] PR #{pr} already carries this deferral for {(head_sha or '')[:8]}")
        return
    text = (f"{marker}\n\n**Not auto-merged.** The run is done, but GitHub will not take the merge yet:\n\n"
            f"- reason: {reason}\n\n"
            f"Unblock it and the next green run merges it: a conflicting or stale branch needs a rebase "
            f"(the rebase bot does this every six hours), a required review needs an approving review, a "
            f"pending check needs the run to finish, and `do-not-merge` is the human hold — remove it when "
            f"the review is done.\n\n"
            f"`make auto-merge-explain PR={pr} REPO={repo}` prints the same verdict at any time.")
    _gh(gh, ["pr", "comment", str(pr), "--repo", repo, "--body", text])


def merge(gh: str, repo: str, pr: int, head_sha: str, delete_branch: bool = True) -> str:
    """Squash-merge exactly the validated commit; delete the branch only when it is in THIS repo."""
    argv = ["pr", "merge", str(pr), "--repo", repo, "--squash"]
    if delete_branch:
        argv.append("--delete-branch")
    argv += ["--match-head-commit", head_sha]
    return _gh(gh, argv)


def _same_repo(state: dict, repo: str) -> bool:
    head_repo = ((state.get("headRepository") or {}).get("nameWithOwner") or "").lower()
    return not head_repo or head_repo == repo.lower()


def _merge(gh: str, repo: str, pr: int, head_sha: str, state: dict, dry: bool) -> int:
    same = _same_repo(state, repo)
    keeps = " (its branch stays in the fork)" if not same else ""
    if dry:
        print(f"[auto-merge] would squash-merge PR #{pr} at {(head_sha or '')[:8]}{keeps}")
        return 0
    print(f"[auto-merge] merging PR #{pr} at {(head_sha or '')[:8]} (green + CLEAN){keeps}")
    print(merge(gh, repo, pr, head_sha, delete_branch=same).strip())
    return verify_closure.verify(gh, repo, pr)


def run(gh: str, repo: str, pr: int, head_sha: str, dry: bool = False,
        approve_when_review_required: bool = False) -> int:
    state = pr_state(gh, repo, pr)
    fields = ("state", "isDraft", "mergeable", "mergeStateStatus", "reviewDecision", "headRefOid")
    print(f"[auto-merge] PR #{pr}: " + json.dumps({k: state.get(k) for k in fields}))
    reason = decide(state, head_sha)
    if reason and approve_when_review_required and review_blocked(state):
        blocked = try_approve(gh, repo, pr, state, dry=dry)
        if blocked is None:
            if dry:
                return 0
            state = pr_state(gh, repo, pr)
            reason = decide(state, head_sha)
            if reason is None:
                return _merge(gh, repo, pr, head_sha, state, dry)
        else:
            reason = blocked
    if reason:
        defer(gh, repo, pr, head_sha, reason, dry=dry)
        return 0
    return _merge(gh, repo, pr, head_sha, state, dry)


def explain(gh: str, repo: str, pr: int, head_sha: str = "") -> int:
    """The same decision, printed for a human. Writes nothing."""
    state = pr_state(gh, repo, pr)
    fields = ("state", "isDraft", "mergeable", "mergeStateStatus", "reviewDecision", "headRefOid",
              "headRepository")
    print(f"[auto-merge] PR #{pr}: " + json.dumps({k: state.get(k) for k in fields}))
    print(f"[auto-merge] author: {((state.get('author') or {}).get('login') or 'unknown')}")
    reason = decide(state, head_sha)
    if reason is None:
        print(f"[auto-merge] verdict: would merge PR #{pr}{' (fork head: branch kept)' if not _same_repo(state, repo) else ''}")
        return 0
    if review_blocked(state):
        print(f"[auto-merge] verdict: would approve with the owner PAT, then merge — IF the approving "
              f"account differs from the author and the author is one of {', '.join(ALLOWED_AUTHORS)} "
              f"(the job checks both at run time)")
        print(f"[auto-merge] note: {reason}")
        return 0
    print(f"[auto-merge] verdict: defers to a human — {reason}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="auto_merge", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("auto-merge", help="merge the PR when this run is green and the PR is CLEAN")
    m.add_argument("--repo", required=True)
    m.add_argument("--pr", type=int, required=True)
    m.add_argument("--head-sha", default="", help="the head commit this run validated")
    m.add_argument("--gh", default="gh")
    m.add_argument("--dry", action="store_true", help="print the decision, merge nothing")
    m.add_argument("--approve-when-review-required", action="store_true",
                   help="approve a green, review-blocked PR with the other allowed identity, then merge")
    e = sub.add_parser("explain", help="print the merge verdict for a PR; writes nothing")
    e.add_argument("--repo", required=True)
    e.add_argument("--pr", type=int, required=True)
    e.add_argument("--head-sha", default="")
    e.add_argument("--gh", default="gh")
    args = p.parse_args(argv)
    if args.cmd == "explain":
        return explain(args.gh, args.repo, args.pr, args.head_sha)
    return run(args.gh, args.repo, args.pr, args.head_sha, args.dry, args.approve_when_review_required)


if __name__ == "__main__":
    raise SystemExit(main())
