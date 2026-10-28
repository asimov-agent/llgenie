#!/usr/bin/env python3
"""Resolve the open pull request a finished CI run belongs to (issue #508).

`.github/workflows/auto-merge.yml` is a `workflow_run` workflow, so GitHub hands it a **run id**, not a
PR number: the run must be mapped back to its pull request before anything can be merged. Two sources,
in this order:

  1. the REST run object's `pull_requests` array;
  2. the head branch plus head owner, through a PR search — the ONLY source that works for a fork head,
     because `gh pr list --head owner:branch` matches same-repo branches only.

Source 1 has a trap, measured on run `39735179724`. For a fork `pull_request` run the endpoint 404s and
`gh api` prints the error **body to stdout**, so

    number=$(gh api "repos/$REPO/actions/runs/$RUN_ID/pull_requests" --jq '.[0].number // empty' || true)

yields `{"message": "Not Found", "status": "404"}` — non-empty, so a `[ -z "$number" ]` guard passes, the
fork fallback never runs, and that multi-line blob is then appended to `$GITHUB_OUTPUT`, which GitHub
refuses ("Invalid format"). The step dies and `make auto-merge` never runs. So a value is a PR number
ONLY when it is digits: everything else — a 404 body, an error line, an empty answer — is "no answer"
and falls through to the next source. Nothing resolving is a loud failure, never an empty value: a green
PR must not be silently dropped.

Commands (stdlib only, the GitHub API only through a `gh` on PATH):

    resolve --repo R --run-id N --head-owner O --head-branch B [--allow-none] [--gh gh]

The resolved number is written as the single line `number=<n>` to the file named by `$GITHUB_OUTPUT`
when that variable is set (the workflow's `id: pr` output), and printed as that same line otherwise.

Two callers ask the same question and differ on ONE thing, so the difference is a flag and not a second
resolver. The merge gate (`auto-merge.yml`, via `make auto-merge-resolve`) must never drop a green PR, so
nothing resolving is a loud failure. The fix-bot's sweep (`fix-bot.yml`, via `make fix-bot-resolve`) is
repairing a PR that a failed run pointed at: when that PR has already merged or closed, there is simply
nothing to repair, and the sweep must end cleanly — measured in issue #629, where a landed PR
(`fix/engine-gate-strict`, PR #627) turned the fix-bot's own run red. `--allow-none` is that answer.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

#: The owner is a login from the run object, never shell-expanded: it is passed to `gh` as argv.
_OWNER_JQ = '.[] | select(.headRepositoryOwner.login=="{}") | .number'
#: The same filter for a PR in ANY state (issue #897), joined into "<number> <state>".
_LANDED_JQ = (r'[.[] | select(.state != "OPEN")] | first | "\(.number) \(.state)"')
#: The search-form filter for the SAME question (#897): `gh pr list --search head:<branch>
#: --state all`, rendered as "<number> <state>" for the PR whose head owner we were given.
_LANDED_SEARCH_JQ = ('.[] | select(.headRepositoryOwner.login == "{}") | "\\(.number) \\(.state)"')




class ResolutionError(RuntimeError):
    """No open pull request could be resolved for the run."""


def _gh(gh: str, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run([gh, *args], capture_output=True, text=True)


def _first_number(text: str) -> int | None:
    """The first line that is a bare number; anything else (an error body, a message) is no answer."""
    for line in text.splitlines():
        token = line.strip()
        if token.isdigit():
            return int(token)
    return None


def run_pr_number(repo: str, run_id: int, gh: str = "gh") -> int | None:
    """The PR the run reports on, or None when the endpoint has no answer (a fork run 404s)."""
    done = _gh(gh, ["api", f"repos/{repo}/actions/runs/{run_id}/pull_requests",
                    "--jq", ".[0].number // empty"])
    return _first_number(done.stdout)


def open_pr_for_head(repo: str, head_owner: str, head_branch: str, gh: str = "gh") -> int | None:
    """The open PR whose head is `head_owner:head_branch` — the fork-head source."""
    done = _gh(gh, ["pr", "list", "--repo", repo, "--search", f"head:{head_branch}", "--state", "open",
                    "--json", "number,headRepositoryOwner", "--jq", _OWNER_JQ.format(head_owner)])
    return _first_number(done.stdout)


def landed_pr_for_head(repo: str, head_owner: str, head_branch: str,
                       gh: str = "gh") -> "tuple[int, str] | None":
    """The CLOSED or MERGED PR whose head is this branch — an answer, not a drop (issue #897).

    A completed `CI` run can arrive after its PR was merged or closed (a bot branch that landed, a branch
    that was abandoned). There is nothing to merge and nothing a human can do, so the merge gate must end
    cleanly; the message still names the PR and its state, so the log says which case it was.

    TWO sources, in this order, for the same reason `resolve()` has two: the REST filter
    `head=<owner>:<branch>` is exact when the head lives in this repository, and a **fork** head is the
    case the search form handles. Measured on 2026-10-28: `head=asimov-agent:ci/844-…` answers
    `867 closed`, while `head=andyholst:ci/844-…` answers nothing for the same PR, so a single-source
    lookup would miss half the heads this repository actually produces (12 of the last 40 PRs are forks).
    """
    done = _gh(gh, ["api", f"repos/{repo}/pulls?state=all&head={head_owner}:{head_branch}&per_page=100",
                    "--jq", _LANDED_JQ])
    found = _first_landed(done.stdout)
    if found:
        return found
    # the search form: it resolves a head whose PR was opened from another repository
    done = _gh(gh, ["pr", "list", "--repo", repo, "--search", f"head:{head_branch}", "--state", "all",
                    "--json", "number,state,headRepositoryOwner", "--jq", _LANDED_SEARCH_JQ.format(head_owner)])
    return _first_landed(done.stdout)


def _first_landed(stdout: str) -> "tuple[int, str] | None":
    """`"<number> <state>"` from a `gh` answer, or None when the answer names no PR."""
    lines = [line.strip() for line in (stdout or "").splitlines() if line.strip()]
    if not lines:
        return None
    number, _, state = lines[0].partition(" ")
    return (int(number), (state.strip() or "UNKNOWN")) if number.isdigit() else None


def resolve(repo: str, run_id: int, head_owner: str, head_branch: str, gh: str = "gh") -> int:
    """The PR number for the run, from the run object first and the head branch second."""
    number = run_pr_number(repo, run_id, gh)
    if number is None:
        number = open_pr_for_head(repo, head_owner, head_branch, gh)
    if number is None:
        raise ResolutionError(
            f"no open pull request for run {run_id} (head {head_owner}:{head_branch}) - "
            "nothing to merge, and a green PR must never be silently dropped")
    return number


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve the open PR a finished CI run belongs to.")
    parser.add_argument("command", choices=["resolve"])
    parser.add_argument("--repo", required=True, help="owner/repo of the BASE repository")
    parser.add_argument("--run-id", required=True, type=int, help="the finished CI run id")
    parser.add_argument("--head-owner", required=True, help="the run's head repository owner")
    parser.add_argument("--head-branch", required=True, help="the run's head branch")
    parser.add_argument("--allow-none", action="store_true",
                        help="answer 'no open PR' with exit 0 and an empty `number=` line (the fix-bot's "
                             "sweep: a PR that already landed is nothing to repair); without it nothing "
                             "resolving is a loud failure (the merge gate)")
    parser.add_argument("--gh", default="gh", help="the gh binary to call (default: gh from PATH)")
    args = parser.parse_args(argv)

    label = "fix-bot-resolve" if args.allow_none else "auto-merge-resolve"
    try:
        number = resolve(args.repo, args.run_id, args.head_owner, args.head_branch, args.gh)
    except ResolutionError as exc:
        if not args.allow_none:
            # issue #897: a head whose PR already merged or closed is a non-event, not a dropped green
            # PR - and a red run for it is a control that fires when nothing is wrong.
            landed = landed_pr_for_head(args.repo, args.head_owner, args.head_branch, args.gh)
            if landed:
                number, state = landed
                print(f"[auto-merge-resolve] nothing to merge: PR #{number} for head "
                      f"{args.head_owner}:{args.head_branch} is {state} (issue #897)", file=sys.stderr)
                return _emit(label, "", args)
            print(f"[auto-merge-resolve] {exc}", file=sys.stderr)
            return 1
        # The fix-bot's own case (issue #629): the run's PR already merged or closed, so there is no
        # branch left to repair. That is an answer, not a failure - the sweep then picks whatever PR
        # deserves the bot, exactly as its scheduled form does.
        print(f"[fix-bot-resolve] no open pull request for run {args.run_id} "
              f"(head {args.head_owner}:{args.head_branch}) - nothing to repair", file=sys.stderr)
        return _emit(label, "", args)

    return _emit(label, str(number), args)


def _emit(label: str, number: str, args: argparse.Namespace) -> int:
    """Write the single `number=<n>` line (empty for the allowed-none answer) to `$GITHUB_OUTPUT`."""
    line = f"number={number}"
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        if number:
            print(f"[{label}] resolved PR #{number} for run {args.run_id} "
                  f"(head {args.head_owner}:{args.head_branch})")
        else:
            print(f"[{label}] resolved no PR for run {args.run_id} "
                  f"(head {args.head_owner}:{args.head_branch})")
    else:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
