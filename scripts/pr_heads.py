#!/usr/bin/env python3
"""Report pull requests whose head lives in another repository (issue #910).

Agents push branches to the **base** repository (`asimov-agent/llgenie`). A PR whose head is a fork
(`andyholst/llgenie`) is a *cross-repository* PR, and it costs three things this repository has already
paid for once:

* a `pull_request` run **from a fork gets no repository secrets** — the empty `secrets.BUMP_TOKEN` that made
  the old in-workflow merge job report `success` while merging nothing (#481), which is why `auto-merge.yml`
  is a `workflow_run` workflow;
* **approval** is a different shape: `github-actions[bot]` with `permissions: pull-requests: write` can
  approve a PR authored by `andyholst`, but a fork head drags in the fork's own review semantics;
* **sweeps need two remote rules** (push back to the PR's own head, never push a fork head to upstream), and
  the ambiguity between them has already produced near-misses.

So this is a REPORT, not a gate: the fifteen existing cross-repository PRs are legitimate and merge as they
are, and failing the build over them would teach the next person to skip the check. What it must not do is
stay silent, because silence is how new work keeps taking the fork path.

Usage:
    pr_heads.py report [--repo R] [--gh gh]     # every open PR, grouped, cross-repo ones explained
    pr_heads.py check  [--repo R] [--gh gh]     # same read, exit 1 ONLY when a NEW cross-repo PR exists
                                                # (never: it is a warning with a reason, see above)

Exit codes: 0 always for `report`; 0 for `check` unless `--strict` is given, which turns reported
cross-repository PRs into a failure for a caller that has decided they are unacceptable.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

#: The repository agents push to, and the one whose PRs are the normal case.
BASE_REPO = "asimov-agent/llgenie"

#: Why the same-repo path is the rule — quoted in the report so the warning is actionable, not a scold.
REASON = (
    "a fork `pull_request` run gets no repository secrets (empty BUMP_TOKEN, #481) and approval follows the "
    "fork's own review semantics, so the same-repo path is the one that can be approved and merged by this "
    "repository's own automation"
)
REMEDY = (
    "push the branch to asimov-agent/llgenie next time (`git push upstream HEAD:<branch>` — see the remotes "
    "table in docs/BOTS.md); this PR is not blocked and needs no action"
)


def _gh(gh: str, args: list[str]) -> str:
    r = subprocess.run([gh, *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"[pr-heads] {gh} {' '.join(args)} failed ({r.returncode}): {r.stderr.strip()}")
    return r.stdout


def open_prs(gh: str = "gh", repo: str = BASE_REPO, limit: int = 200) -> list[dict]:
    """Every open PR with the fields that decide same-repo vs cross-repo, as one API call."""
    out = _gh(gh, ["pr", "list", "--repo", repo, "--state", "open", "--limit", str(limit),
                   "--json", "number,title,author,headRepositoryOwner,isCrossRepository,headRefName"])
    return json.loads(out or "[]")


def classify(prs: list[dict]) -> tuple[list[dict], list[dict]]:
    """`(same_repo, cross_repo)`; the second group is what the report explains.

    `isCrossRepository` is GitHub's own answer and is used when present — deriving it from the owner login
    would be a second opinion about a fact the API already states.
    """
    same: list[dict] = []
    cross: list[dict] = []
    for pr in prs:
        flag = pr.get("isCrossRepository")
        if flag is None:
            owner = ((pr.get("headRepositoryOwner") or {}).get("login") or "")
            flag = owner.lower() != BASE_REPO.split("/")[0].lower()
        (cross if flag else same).append(pr)
    return same, cross


def _author(pr: dict) -> str:
    return ((pr.get("author") or {}).get("login") or "unknown")


def report(prs: list[dict], repo: str = BASE_REPO) -> str:
    """The text a reader gets: the counts, then every cross-repository PR with its reason and its remedy."""
    same, cross = classify(prs)
    lines = [f"[pr-heads] {len(prs)} open PR(s) in {repo}: {len(same)} same-repository, "
             f"{len(cross)} CROSS-REPOSITORY"]
    if cross:
        lines.append("")
        lines.append("cross-repository heads — reported, not blocked:")
        for pr in sorted(cross, key=lambda p: p.get("number") or 0):
            owner = ((pr.get("headRepositoryOwner") or {}).get("login") or "?")
            lines.append(f"  #{pr.get('number')} by @{_author(pr)} — head {owner}:{pr.get('headRefName')}")
        lines.append("")
        lines.append(f"why it matters: {REASON}")
        lines.append(f"remedy: {REMEDY}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("report", "check"):
        p = sub.add_parser(name)
        p.add_argument("--repo", default=BASE_REPO)
        p.add_argument("--gh", default="gh")
        p.add_argument("--limit", type=int, default=200)
        if name == "check":
            p.add_argument("--strict", action="store_true",
                           help="exit 1 when any cross-repository PR exists (off by default: #910 is a "
                                "warning with a reason, because the existing PRs are legitimate)")
    args = parser.parse_args(argv)

    prs = open_prs(args.gh, args.repo, args.limit)
    print(report(prs, args.repo))
    if args.command == "report":
        return 0
    _, cross = classify(prs)
    if cross and args.strict:
        print(f"[pr-heads] FAIL: {len(cross)} cross-repository PR(s) and --strict was given", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
