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
  * a bot's REVIEW VERDICT is a comment marker, never an approval (issue #852). Every bot pushes with the
    owner's token, so `gh pr review --approve` on its own PR is refused and `reviewDecision` can never leave
    `REVIEW_REQUIRED`; a complete verdict written only in prose was therefore invisible to this decision and
    the PR sat `BLOCKED` forever. `scripts/bot_verdict.py` owns the marker
    (`<!-- bot-verdict: head=<sha> verdict=<approve|changes> reviewer=<login> -->`), and this decision
    accepts it ONLY when the head it names equals the PR's CURRENT `headRefOid`: a verdict on an older
    commit describes a tree that is not merging, so a stale one is refused. The merge then uses `--admin`
    (the review block cannot be moved by an approval a bot is allowed to post), and a refusal is a
    deferral with the reason on the PR, never a red run;
  * every deferral posts ONE comment per head SHA (`<!-- auto-merge: deferred <sha> -->`) carrying the reason
    and what would unblock it, so "why is this not merged?" is answerable from the PR, not from a run log;
  * a red check-run on the head is not merged, whatever `mergeStateStatus` says (issue #1386). `BLOCKED` on
    #1401 was the required review, while `scope` had already failed; the recheck approved that and
    `gh pr merge --admin` bypassed protection. A conclusion of `failure`, `timed_out`,
    `startup_failure`, `cancelled` or `neutral` defers (a cancelled run is a killed CI, and the
    `neutral` is `ci_verdict`'s superseded-head verdict — neither is a green pipeline; #1250 Finding B).
    `skipped` alone is not red: a docs-only head has no `linux` job (#843).

The merge itself is `gh pr merge --squash [--delete-branch] --match-head-commit <sha>` with the OWNER PAT by
the caller (a merge with the job's own token starts no workflows), and `--delete-branch` is omitted for a fork
head (the base token cannot delete a branch in the fork). Afterwards `scripts/verify_closure.py` proves the
body's `closes #n` bound.

The ORDER a review block takes is the point (issue #524): approve as the identity that is NOT the author, then
merge normally — the path `trending-local-llms` gets for free because its `master` carries no review rule.
`--admin` is only the last resort, for a PR whose author IS the merge token's account: GitHub refuses both the
self-approval and the bypass wherever the rule is enforced for admins (measured on PR #523, run 39816912388).
An optional `APPROVER_TOKEN` supplies the other identity for those bot-authored PRs; without it the run defers
with the reason ON the PR instead of dying red.

Commands (stdlib only, the GitHub API only through a `gh` on PATH):
  auto-merge --repo R --pr N --head-sha S [--dry] [--approve-when-review-required] [--gh gh]
  explain    --repo R --pr N [--head-sha S] [--gh gh]      print the verdict, write nothing
  red-check  --repo R --pr N [--gh gh]                     exit 1 when the head has a red check
  alert-merged-red --repo R [--limit N] [--dry] [--gh gh]  comment once on a merged red head
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time

import verify_closure

#: A bot's review verdict is a comment marker owned by `scripts/bot_verdict.py` — never an approval
#: (issue #852). `decide()` reads it, and accepts it only at the PR's CURRENT head.
import bot_verdict

REQUIRED_STATE = "OPEN"
REQUIRED_MERGEABLE = "MERGEABLE"
REQUIRED_MERGE_STATE = "CLEAN"
HOLD_LABEL = "do-not-merge"
#: The two identities this repository allows on a PR (AGENTS.md: `Andy Holst`, `Asimov Agent`), as logins.
ALLOWED_AUTHORS = ("andyholst", "asimov-agent")
#: Owners whose fork may supply a head. Every agent PR is pushed to `andyholst/llgenie`; a third-party fork
#: is somebody else's code and is never merged by this job, however green its run looks.
TRUSTED_HEAD_OWNERS = ("andyholst",)
#: Who may OPEN a PR this job merges: the repo owner, a collaborator with write (or more), or the bot.
#: This is the same gate `ci.yml`'s `guard` job applies to a run (issue #122). A green PR from anyone else
#: stays manual, even when its head happens to live in a trusted fork.
WRITE_PERMISSIONS = ("admin", "maintain", "write")
BOT_LOGINS = ("github-actions[bot]", "app/github-actions")
#: One deferral comment per head SHA — re-posted only when the head moves.
DEFERRAL_MARKER = "<!-- auto-merge: deferred {} -->"
#: One comment per head on a PR that already merged while that head's pipeline was red (issue #1386).
MERGED_RED_MARKER = "<!-- merged-over-red: {} -->"
#: One MERGE announcement per head SHA (fleet rule 14, issue #873): the merger must publish what it acted on.
#: A merger that merges silently is the same defect as two lanes on one branch — the next reader cannot tell
#: work from coincidence, and "approval is not the blocker, scheduling is" stays an assertion instead of a record.
MERGE_MARKER = "<!-- auto-merge: merged {} -->"
#: Every `gh pr view --json` field name this module requests, in ONE place (issue #513).
#: `authorAssociation` is deliberately absent: `gh pr view` has no such field, and asking for it made
#: every run die with `Unknown JSON field: "authorAssociation"` before `decide()` was ever reached.
#: `tests/test_auto_merge.py` asserts every name here is in `tests/fixtures/gh-pr-view-fields.json`,
#: which is captured from gh's own `gh pr view --json __probe__` allowlist.
PR_VIEW_STATE_FIELDS = ("state", "isDraft", "mergeable", "mergeStateStatus", "headRefOid", "labels",
                        "headRepository", "author", "reviewDecision")
#: Requested separately, only for the one-comment-per-head deferral dedupe.
PR_VIEW_COMMENT_FIELDS = ("comments",)
PR_VIEW_FIELDS = PR_VIEW_STATE_FIELDS + PR_VIEW_COMMENT_FIELDS


def _gh(gh: str, args: list[str], token: str = "") -> str:
    """Run `gh`. A `token` is passed through the ENVIRONMENT only — never on the command line, where
    `ps` and a run log would carry it (the credential rule in AGENTS.md)."""
    env = None
    if token:
        env = {**os.environ, "GH_TOKEN": token}
    r = subprocess.run([gh, *args], capture_output=True, text=True, env=env)  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
    if r.returncode != 0:
        raise SystemExit(f"[auto-merge] {gh} {' '.join(args)} failed ({r.returncode}): {r.stderr.strip()}")
    return r.stdout


def pr_state(gh: str, repo: str, pr: int) -> dict:
    """What GitHub says about this PR right now: the merge decision is read from here, in one call.

    The `comments` are part of the read because a bot's review verdict IS a comment marker (issue
    #852): the decision needs the thread and the head in the SAME snapshot, or a verdict could be
    matched against a head it was not written for.
    """
    out = _gh(gh, ["pr", "view", str(pr), "--repo", repo, "--json",
                   ",".join(PR_VIEW_FIELDS)])
    return json.loads(out or "{}")


def author_login(state: dict) -> str:
    return ((state.get("author") or {}).get("login") or "").strip()


def _is_bot(login: str) -> bool:
    """True for a bot opener: an App login (`app/github-actions`) or any `…[bot]` login.

    The login is the whole test because `gh pr view` has no `authorAssociation` field (issue #513):
    the old read of that invented field is what killed every run before this decision was reached.
    """
    who = (login or "").strip().lower()
    return who in BOT_LOGINS or who.endswith("[bot]")


def author_may_merge(gh: str, repo: str, state: dict, actor: str = "") -> "str | None":
    """None when the opener is the owner, a write collaborator, or the bot; else the reason.

    A bot PR is opened by `app/github-actions` (or a `…[bot]` login), whose permission endpoint
    answers nothing useful. The CI run's actor is the person or bot that pushed the branch, so that is
    what this checks for a bot author — the same two names `ci.yml`'s guard already checked before the
    run was allowed to finish green.
    """
    login = author_login(state)
    owner = repo.split("/")[0]
    if _is_bot(login):
        who = (actor or "").strip()
        if not who:
            return (f"PR author `{login}` is a bot, and this run did not say who triggered it "
                    f"(ACTOR is empty) — a bot PR is merged only for the owner, a write collaborator, "
                    f"or the bot itself")
        return _permission_allows(gh, repo, who, owner, kind="actor")
    who = login or (actor or "").strip()
    if not who:
        return "PR has no author and this run named no actor — nothing to authorise a merge against"
    return _permission_allows(gh, repo, who, owner, kind="author")


def _permission_allows(gh: str, repo: str, login: str, owner: str, kind: str) -> "str | None":
    if login.lower() == owner.lower() or _is_bot(login):
        return None
    perm = _permission(gh, repo, login)
    if perm in WRITE_PERMISSIONS:
        return None
    return (f"the {kind} `{login}` is not the owner, a write collaborator, or the bot "
            f"(permission: {perm or 'none'}) — this job merges only those")


def _permission(gh: str, repo: str, login: str) -> str:
    """The collaborator permission, or empty when GitHub has none (a bot, a stranger)."""
    r = subprocess.run(  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
        [gh, "api", f"repos/{repo}/collaborators/{login}/permission", "--jq", ".permission"],
        capture_output=True, text=True)
    if r.returncode != 0:
        return ""
    return (r.stdout or "").strip().lower()


def decide(state: dict, head_sha: str, hold_label: str = HOLD_LABEL,
           repo_owner: str = "") -> "str | None":
    """None when the PR may be merged; otherwise the reason it is deferred to a human.

    A review block is cleared by a BOT VERDICT at the PR's current head (issue #852), never by a
    GitHub approval: a bot pushes with the owner's token, so `gh pr review --approve` on its own PR is
    refused and `reviewDecision` can never leave `REVIEW_REQUIRED`. The verdict's marker names the sha
    it reviewed, and it counts only when that sha equals `headRefOid` right now — a verdict on an older
    commit describes a tree that is not merging, so a stale one is refused by the same rule the run's
    own head check applies.
    """
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
    current_head = (state.get("headRefOid") or "").strip().lower()
    verdict = bot_verdict.verdict_for_head(state.get("comments") or [], current_head)
    if verdict and verdict["verdict"] in bot_verdict.BLOCKING:
        return (f"a bot verdict at {(current_head or '?')[:8]} requests changes "
                f"(reviewer `{verdict['reviewer']}`)")
    status = (state.get("mergeStateStatus") or "").upper()
    if status != REQUIRED_MERGE_STATE:
        cleared = (status == "BLOCKED" and review_blocked(state) and verdict
                   and verdict["verdict"] in bot_verdict.ACCEPTING)
        if not cleared:
            why = {"DIRTY": "conflicts with main", "BEHIND": "behind main (needs an update)",
                   "BLOCKED": "blocked by a required check or review"}.get(status, "not mergeable yet")
            return f"mergeStateStatus is {status or 'UNKNOWN'} ({why})"
    head_repo = ((state.get("headRepository") or {}).get("nameWithOwner") or "")
    if head_repo and repo_owner:
        owner, _, _ = head_repo.partition("/")
        if owner.lower() != (repo_owner or "").lower() and owner.lower() not in TRUSTED_HEAD_OWNERS:
            return (f"head is `{head_repo}`, a third-party fork this job does not merge "
                    f"(only this repo or {', '.join(TRUSTED_HEAD_OWNERS)})")
    if head_sha and (state.get("headRefOid") or "") != head_sha:
        return (f"the head moved since this run started "
                f"({(state.get('headRefOid') or '')[:8]} != {head_sha[:8]}); the newer run decides")
    return None


def review_blocked(state: dict) -> bool:
    """True only for the one procedural block a bot may clear: a required review, everything else green."""
    return ((state.get("mergeable") or "").upper() == REQUIRED_MERGEABLE
            and (state.get("mergeStateStatus") or "").upper() == "BLOCKED"
            and (state.get("reviewDecision") or "").upper() == "REVIEW_REQUIRED")


# A check-run conclusion that is a red pipeline. `cancelled` and `neutral` ARE red (issue #1250
# Finding B): a cancelled run is a CI run killed mid-flight — not a docs-only head — and a `neutral`
# check-run is what `ci_verdict` posts for a superseded head (never `success`); neither may walk the
# merge gate as if it were green. `skipped` stays non-red: a docs-only pull request has no `linux`
# job, and `linux` on #1385 was skipped beside real failures — that is the one legitimate "no verdict".
RED_CONCLUSIONS = frozenset({"failure", "timed_out", "startup_failure", "cancelled", "neutral"})
_RUN_JOB = re.compile(r"/actions/runs/(\d+)/job/(\d+)")
_RUN_ONLY = re.compile(r"/runs/(\d+)")


def _check_runs(gh: str, repo: str, sha: str) -> "list | None":
    """The head's check-runs, or None when the payload is not a list. Raises SystemExit when `gh` fails."""
    out = _gh(gh, ["api", f"repos/{repo}/commits/{sha}/check-runs?per_page=100",
                   "--jq", "[.check_runs[] | {name: .name, conclusion: .conclusion, details_url: .details_url}]"])
    try:
        runs = json.loads(out or "[]")
    except json.JSONDecodeError:
        return None
    return runs if isinstance(runs, list) else None


def _failed_step(gh: str, repo: str, job_id: str) -> str:
    """The first failing step of an Actions job, or "" when the job payload cannot be read."""
    try:
        out = _gh(gh, ["api", f"repos/{repo}/actions/jobs/{job_id}",
                       "--jq", '[.steps[] | select(.conclusion=="failure") | .name][0] // ""'])
    except SystemExit:
        return ""
    return (out or "").strip().strip('"')


def failing_checks(gh: str, repo: str, sha: str) -> "str | None":
    """The first red check on this commit, or None when every concluded check passed.

    `mergeStateStatus` is not this. A failed `scope` job left #1401 `BLOCKED` on the review, and the
    recheck then called the pull request green and merged it with `--admin` (issue #1386). The check
    runs are the head pipeline. A conclusion that is not in `RED_CONCLUSIONS` is not a red: `skipped`
    stays mergeable (a docs-only head has no `linux` job), but `cancelled` and `neutral` are red
    (#1250 Finding B) — a killed run or a superseded-head neutral is not a green verdict, and a check
    that has not concluded yet is not a failure.
    """
    if not sha:
        return None
    try:
        runs = _check_runs(gh, repo, sha)
    except SystemExit as exc:
        return f"head {sha[:8]} check-runs could not be read ({exc})"
    if runs is None:
        return f"head {sha[:8]} check-runs were not readable"
    red = [r for r in runs if str((r or {}).get("conclusion") or "").lower() in RED_CONCLUSIONS]
    if not red:
        return None
    first = red[0] or {}
    url = str(first.get("details_url") or "")
    where = ""
    job = _RUN_JOB.search(url)
    if job:
        step = _failed_step(gh, repo, job.group(2))
        where = f", run {job.group(1)}, job {job.group(2)}"
        if step:
            where += f", step `{step}`"
    else:
        only = _RUN_ONLY.search(url)
        if only:
            where = f", run {only.group(1)}"
        elif url:
            where = f", {url}"
    return (f"head {sha[:8]} has a red check `{first.get('name')}` "
            f"({first.get('conclusion')}{where}) — a red pipeline is not merged (issue #1386)")


#: The account a workflow's own `GITHUB_TOKEN` acts as. `GET /user` cannot be read with an installation
#: token (403 "Resource not accessible by integration"), so the identity is not askable — and it does not
#: have to be, because it is deterministic. Naming it explicitly is what lets the guard below refuse a PR
#: this bot opened itself, instead of guessing and approving it (issue #874).
WORKFLOW_BOT = "github-actions[bot]"


def token_login(gh: str, token: str = "") -> str:
    """The account a token belongs to; "" when it cannot be asked (an installation token cannot)."""
    try:
        return _gh(gh, ["api", "user", "--jq", ".login"], token=token).strip()
    except SystemExit:
        return ""


def approve(gh: str, repo: str, pr: int, token: str = "") -> str:
    body = ("Approved by the repo's `auto-merge` job (issue #491): the run is green and the only thing "
            "missing was a required review. It merges immediately if the state becomes CLEAN; "
            "`do-not-merge` holds a PR at any time.")
    return _gh(gh, ["pr", "review", str(pr), "--repo", repo, "--approve", "--body", body], token=token)


def try_approve(gh: str, repo: str, pr: int, state: dict, dry: bool = False,
                approver_token: str = "") -> "str | None":
    """Approve a review-blocked green PR with the OTHER allowed identity; None on success, else the reason.

    GitHub refuses a pull request approving its own author, so the identity that approves must differ from
    the one that opened the PR. That is the normal case here (`andyholst` opens, the `asimov-agent` PAT
    approves); when the PR author IS the merge token's account — every bot PR — an optional second token
    (`APPROVER_TOKEN`) supplies the other identity. Without one, the caller falls back to the admin bypass.
    """
    author = ((state.get("author") or {}).get("login") or "").strip()
    me = token_login(gh)
    token = ""
    if author and author.lower() == me.lower():
        if not approver_token:
            return (f"a required review is missing, and the PR's author (`{author}`) is the merge token's own "
                    f"account — GitHub refuses a self-approval, so a human must approve it "
                    f"(or set APPROVER_TOKEN to the other allowed identity)")
        # The workflow's own token cannot answer `GET /user`; its identity is the runner's bot account.
        me = token_login(gh, token=approver_token) or WORKFLOW_BOT
        token = approver_token
        if author.lower() == me.lower():
            return (f"a required review is missing, and both tokens belong to `{me}` — GitHub refuses a "
                    f"self-approval, so a human must approve it")
    if author.lower() not in ALLOWED_AUTHORS and not _is_bot(author):
        return (f"a required review is missing, and the author `{author or 'unknown'}` is not one of this "
                f"repo's identities ({', '.join(ALLOWED_AUTHORS)}) or its own bot — a bot does not approve "
                f"a stranger's PR")
    if dry:
        print(f"[auto-merge] would approve PR #{pr} as `{me}` (a required review is the only blocker)")
        return None
    print(f"[auto-merge] PR #{pr} is green but blocked by a required review — approving as `{me}` "
          f"(authored by `{author}`)")
    print(approve(gh, repo, pr, token=token).strip())
    return None


def pr_comments(gh: str, repo: str, pr: int) -> list[str]:
    out = _gh(gh, ["pr", "view", str(pr), "--repo", repo, "--json",
                   ",".join(PR_VIEW_COMMENT_FIELDS)])
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


def merge(gh: str, repo: str, pr: int, head_sha: str, delete_branch: bool = True,
          admin: bool = False) -> str:
    """Squash-merge exactly the validated commit; delete the branch only when it is in THIS repo.

    `admin` is the bypass for a required review. GitHub refuses a self-approval, and the owner PAT is
    the account that opens these PRs, so an approval can never clear that block. The bypass is passed
    only after the author gate has already accepted the opener.
    """
    argv = ["pr", "merge", str(pr), "--repo", repo, "--squash"]
    if delete_branch:
        argv.append("--delete-branch")
    if admin:
        argv.append("--admin")
    argv += ["--match-head-commit", head_sha]
    return _gh(gh, argv)


def _same_repo(state: dict, repo: str) -> bool:
    head_repo = ((state.get("headRepository") or {}).get("nameWithOwner") or "").lower()
    return not head_repo or head_repo == repo.lower()


def announce_merge(gh: str, repo: str, pr: int, head_sha: str, admin: bool = False,
                   dry: bool = False) -> None:
    """Say on the PR what was merged, at which sha, by which run, and why it was allowed (rule 14, #873).

    Idempotent per head sha, like the deferral: a recheck that finds the PR already merged must not post twice.
    """
    marker = MERGE_MARKER.format(head_sha)
    if not (head_sha or "").strip():
        # An empty sha makes the marker `<!-- auto-merge: merged  -->`, which matches every other empty-sha
        # announcement, and "head sha judged: ``" is evidence that identifies nothing. Refuse loudly: rule 14
        # exists so a reader can check WHICH tree was merged, and a comment that cannot answer that is noise
        # wearing the shape of an audit line.
        print(f"[auto-merge] PR #{pr}: NOT announcing the merge — no head sha was supplied, so the comment "
              f"could not say which tree was merged (rule 14, #873)", file=sys.stderr)
        return
    if dry:
        print(f"[auto-merge] would announce the merge on PR #{pr} ({marker})")
        return
    if any(marker in body for body in pr_comments(gh, repo, pr)):
        return
    # "unknown" would be a value the merger invented: the docs advertise `make auto-merge` as a local
    # invocation, which has no `GITHUB_RUN_ID`, and a comment claiming a run that does not exist is the same
    # defect as a merge with no comment at all. Say which kind of run it was instead.
    run_id = os.environ.get("GITHUB_RUN_ID")
    actor = f"run `{run_id}`" if run_id else "a local invocation (`make auto-merge`, no `GITHUB_RUN_ID`)"
    how = "green CI run + `mergeStateStatus: CLEAN`"
    if admin:
        how += ", merged with `--admin` because the required review cannot be self-approved"
    text = (f"{marker}\n\n**Merged by `auto-merge`.**\n\n"
            f"- run: {actor}\n"
            f"- head sha judged: `{head_sha}`\n"
            f"- decision: {how}\n\n"
            "Published because a merger that merges silently is the same defect as two lanes on one branch: "
            "the next reader cannot tell work from coincidence (fleet rule 14, issue #873).")
    try:
        _gh(gh, ["pr", "comment", str(pr), "--repo", repo, "--body", text])
    except SystemExit as exc:
        # The merge already happened, so a failure here must not read as "the run failed" without saying
        # what DID: name the merge and the missing record in one line, then re-raise so it stays loud (the
        # run-failure reactor is the consumer). Silence is the defect rule 14 exists to remove; a bare
        # `gh … failed` would charge the merge itself for a comment that never landed.
        print(f"[auto-merge] PR #{pr}: MERGED at {head_sha} but the rule-14 announcement could NOT be posted "
              f"— the PR has no audit line: {exc}", file=sys.stderr)
        raise


def _merge(gh: str, repo: str, pr: int, head_sha: str, state: dict, dry: bool,
          admin: bool = False) -> int:
    same = _same_repo(state, repo)
    keeps = " (its branch stays in the fork)" if not same else ""
    bypass = " (admin: the required review cannot be self-approved)" if admin else ""
    if dry:
        print(f"[auto-merge] would squash-merge PR #{pr} at {(head_sha or '')[:8]}{keeps}{bypass}")
        return 0
    print(f"[auto-merge] merging PR #{pr} at {(head_sha or '')[:8]} (green + CLEAN){keeps}{bypass}")
    print(merge(gh, repo, pr, head_sha, delete_branch=same, admin=admin).strip())
    announce_merge(gh, repo, pr, head_sha, admin=admin)
    return verify_closure.verify(gh, repo, pr)


#: GitHub computes `mergeStateStatus` asynchronously after a review, so the read taken the instant the
#: approval lands still says BLOCKED (issue #531). Poll, bounded, before deciding.
RECHECK_ATTEMPTS = 6
RECHECK_DELAY = 5.0


def settle_mergeable(gh: str, repo: str, pr: int, attempts: int = 0,
                     delay: float = -1.0) -> dict:
    """Wait for GitHub to COMPUTE `mergeable`, instead of reading `UNKNOWN` and giving up (issue #558).

    GitHub computes `mergeable` asynchronously: a read immediately after a run finishes can answer
    `UNKNOWN`, which is neither "conflicts" nor "mergeable". Measured on PR #552 (run 39931464102): the run
    read `mergeable: UNKNOWN`, deferred with "GitHub has not finished computing it", and nothing retried it —
    the PR was green, clean and merged by the next run that happened to look.
    """
    n = attempts or RECHECK_ATTEMPTS
    wait = RECHECK_DELAY if delay < 0 else delay
    state = pr_state(gh, repo, pr)
    for attempt in range(1, n + 1):
        if (state.get("mergeable") or "").upper() != "UNKNOWN":
            return state
        if attempt == n:
            break
        print(f"[auto-merge] PR #{pr}: GitHub has not computed `mergeable` yet "
              f"(UNKNOWN, {attempt}/{n}); waiting instead of deferring")
        time.sleep(wait)
        state = pr_state(gh, repo, pr)
    return state


def wait_for_merge_state(gh: str, repo: str, pr: int, attempts: int = 0,
                         delay: float = -1.0) -> dict:
    """Re-read the PR until its merge state reflects the approval, or the attempts run out.

    A single read right after `gh pr review --approve` reports the PRE-approval state: measured on PR #530
    (run 39892494540) the job approved as `asimov-agent`, read `BLOCKED`, and abandoned the legitimate path
    — while the PR was `APPROVED`/`CLEAN` seconds later (issue #531).
    """
    n = attempts or RECHECK_ATTEMPTS
    wait = RECHECK_DELAY if delay < 0 else delay
    state = pr_state(gh, repo, pr)
    for attempt in range(1, n + 1):
        if (state.get("mergeStateStatus") or "").upper() == REQUIRED_MERGE_STATE:
            return state
        if attempt == n:
            break
        print(f"[auto-merge] PR #{pr}: waiting for the approval to take effect "
              f"(mergeStateStatus {state.get('mergeStateStatus') or 'UNKNOWN'}, {attempt}/{n})")
        time.sleep(wait)
        state = pr_state(gh, repo, pr)
    return state


def _clear_review(gh: str, repo: str, pr: int, head_sha: str, state: dict, dry: bool) -> int:
    """Clear the one procedural block a bot may clear: a required review (issue #524).

    Order matters, and it is the order `trending-local-llms` gets for free: approve as the identity that is
    NOT the author, then merge the validated commit normally. Whichever path merges announces on the PR
    (rule 14, #873). `--admin` is the last resort, because GitHub
    refuses it wherever the review rule is enforced for admins — which is why #491's bypass has never
    merged anything (measured: PR #523, run 39816912388).
    """
    why = try_approve(gh, repo, pr, state, dry=dry,
                      approver_token=(os.environ.get("APPROVER_TOKEN") or "").strip())
    if why is None:
        if dry:
            return 0
        state = wait_for_merge_state(gh, repo, pr)      # bounded: the approval is not instant
        reason = decide(state, head_sha, repo_owner=repo.split("/")[0])
        if reason is None:
            return _merge(gh, repo, pr, head_sha, state, dry)
        # The approval DID land; say so, and name the state it was still stuck in — never `None`.
        why = (f"the approval landed, but the PR did not become mergeable within the wait "
               f"(mergeStateStatus {state.get('mergeStateStatus') or 'UNKNOWN'}: {reason})")
        print(f"[auto-merge] PR #{pr}: {why}")
        # The approval landed and the pull request is still not CLEAN. That is a red or unfinished
        # pipeline (UNSTABLE on #1401 after the scope job failed). `--admin` would skip it. Defer.
        defer(gh, repo, pr, head_sha, why, dry=dry)
        return 0
    print(f"[auto-merge] PR #{pr} cannot be approved: {why}")
    red = failing_checks(gh, repo, head_sha)
    if red:
        defer(gh, repo, pr, head_sha, red, dry=dry)
        return 0
    if dry:
        print(f"[auto-merge] would fall back to --admin for PR #{pr}")
        return 0
    print(f"[auto-merge] PR #{pr}: falling back to --admin (the review cannot be cleared legitimately)")
    try:
        print(merge(gh, repo, pr, head_sha, delete_branch=_same_repo(state, repo), admin=True).strip())
        # Rule 14 (#873): the admin path is a merge too, so it publishes what it acted on. It is called
        # AFTER the merge returned: a refusal raises SystemExit and reaches the deferral below instead,
        # so a run that could not merge never announces one.
        announce_merge(gh, repo, pr, head_sha, admin=True)
    except SystemExit as exc:
        # A refusal here is a policy deferral, not a broken gate: say so ON the PR (the #491 rule) and
        # never let a run that could not merge look like one that chose not to (#513).
        defer(gh, repo, pr, head_sha, f"{why}; the admin merge was refused too: {exc}", dry=dry)
        return 0
    return verify_closure.verify(gh, repo, pr)


def _merge_review_cleared(gh: str, repo: str, pr: int, head_sha: str, state: dict, dry: bool) -> int:
    """Merge a review-blocked PR whose block was cleared by a BOT VERDICT at this head (issue #852).

    The verdict is the review, but GitHub's `reviewDecision` cannot be moved by it (an approval of a
    bot-authored PR is refused by GitHub itself), so the block is a procedural identity block and the
    merge is the `--admin` path that bypasses it. A refusal is a deferral with the reason ON the PR,
    never a red run: a repository that enforces the review rule for admins simply waits for a human.
    """
    red = failing_checks(gh, repo, head_sha or (state.get("headRefOid") or ""))
    if red:
        defer(gh, repo, pr, head_sha, red, dry=dry)
        return 0
    verdict = bot_verdict.verdict_for_head(state.get("comments") or [],
                                           (state.get("headRefOid") or ""))
    who = verdict["reviewer"] if verdict else "unknown"
    if dry:
        print(f"[auto-merge] would merge PR #{pr} at {(head_sha or '')[:8]} on the bot verdict at this "
              f"head (reviewer `{who}`); the required review cannot be self-approved, so the merge uses "
              f"--admin")
        return 0
    print(f"[auto-merge] PR #{pr} is green and review-blocked, with a bot verdict at "
          f"{(head_sha or '')[:8]} from `{who}` — merging on the verdict (--admin: the review block "
          f"cannot be cleared by an approval a bot may post)")
    try:
        print(merge(gh, repo, pr, head_sha, delete_branch=_same_repo(state, repo), admin=True).strip())
    except SystemExit as exc:
        defer(gh, repo, pr, head_sha,
              f"a bot verdict at {(head_sha or '')[:8]} from `{who}` cleared the review, but GitHub "
              f"refused the merge: {exc}", dry=dry)
        return 0
    return verify_closure.verify(gh, repo, pr)


def run(gh: str, repo: str, pr: int, head_sha: str, dry: bool = False,
        approve_when_review_required: bool = False, actor: str = "") -> int:
    state = pr_state(gh, repo, pr)
    if (state.get("mergeable") or "").upper() == "UNKNOWN" and not dry:
        state = settle_mergeable(gh, repo, pr)
    fields = ("state", "isDraft", "mergeable", "mergeStateStatus", "reviewDecision", "headRefOid")
    print(f"[auto-merge] PR #{pr}: " + json.dumps({k: state.get(k) for k in fields}))
    refused = author_may_merge(gh, repo, state, actor=actor)
    if refused:
        defer(gh, repo, pr, head_sha, refused, dry=dry)
        return 0
    red = failing_checks(gh, repo, head_sha or (state.get("headRefOid") or ""))
    if red:
        defer(gh, repo, pr, head_sha or (state.get("headRefOid") or ""), red, dry=dry)
        return 0
    reason = decide(state, head_sha, repo_owner=repo.split("/")[0])
    if reason and approve_when_review_required and review_blocked(state):
        return _clear_review(gh, repo, pr, head_sha, state, dry)
    if reason:
        defer(gh, repo, pr, head_sha, reason, dry=dry)
        return 0
    if review_blocked(state):
        # decide() cleared the review block: only a bot verdict at this head can do that (#852).
        return _merge_review_cleared(gh, repo, pr, head_sha, state, dry)
    return _merge(gh, repo, pr, head_sha, state, dry)


def deferred_for_head(gh: str, repo: str, pr: int, head_sha: str) -> bool:
    """Whether this PR carries a deferral marker for exactly this head (issue #545)."""
    if not head_sha:
        return False
    marker = DEFERRAL_MARKER.format(head_sha[:40])
    return any(marker in body for body in pr_comments(gh, repo, pr))


def recheck(gh: str, repo: str, max_prs: int = 5, dry: bool = False) -> int:
    """Re-evaluate the PRs whose own deferral marker matches their CURRENT head (issue #545).

    A deferral is exit 0 by design, so nothing retries it: the blocker can clear (a secret added, a review
    posted, `do-not-merge` removed, a pending check finished) and the PR stays green and unmerged until a
    push. This sweep closes that hole by running the SAME decision again — no second merge path — only for a
    PR the gate itself deferred at the head it still has. A stale marker (the head moved) is skipped: that
    verdict described a different tree.
    """
    out = _gh(gh, ["pr", "list", "--repo", repo, "--state", "open", "--limit", "100",
                   "--json", "number,headRefOid"])
    prs = json.loads(out or "[]")
    seen = 0
    for pr in prs:
        num = int(pr["number"])
        head = (pr.get("headRefOid") or "")
        if not deferred_for_head(gh, repo, num, head):
            state = pr_state(gh, repo, num)
            if not review_blocked(state):
                print(f"[recheck] #{num}: no deferral marker for {(head or '?')[:8]} — not a retry")
                continue
            # #1401: BLOCKED + REVIEW_REQUIRED while `scope` was already failure. That is not "review
            # is the only blocker", and approving it is what reached `gh pr merge --admin`.
            red = failing_checks(gh, repo, head)
            if red:
                print(f"[recheck] #{num}: {red}")
                defer(gh, repo, num, head, red, dry=dry)
                continue
            if seen >= max_prs:
                print(f"[recheck] cap reached ({max_prs} PRs this sweep); the rest waits for the next one")
                break
            seen += 1
            print(f"[recheck] #{num}: review is the only blocker at {(head or '?')[:8]} — approving")
            if dry:
                print(f"[recheck] #{num}: --dry, decision not run")
                continue
            run(gh, repo, num, head, dry=False, approve_when_review_required=True,
                actor=token_login(gh))
            continue
        if seen >= max_prs:
            print(f"[recheck] cap reached ({max_prs} PRs this sweep); the rest waits for the next one")
            break
        seen += 1
        print(f"[recheck] #{num}: retrying the deferral at {head[:8]}")
        if dry:
            print(f"[recheck] #{num}: --dry, decision not run")
            continue
        # The sweep runs as the repository's own scheduled job, so the token's account is its actor: that is
        # what authorises a bot-opened PR (a bot has no permission endpoint to ask).
        run(gh, repo, num, head, dry=False, approve_when_review_required=True,
            actor=token_login(gh))
    if seen == 0:
        print("[recheck] no deferred PR needs a retry")
    return 0


def alert_merged_red(gh: str, repo: str, limit: int = 20, dry: bool = False) -> int:
    """Comment once on a merged PR whose head check-set was red (issue #1386).

    The merge gate stops the next one. This is the owner-facing record of one that already landed:
    the head sha that was red, the merge commit, and whether that merge commit's own checks are red
    or clear. A later green re-run on the merge commit is not evidence the head was green.
    """
    out = _gh(gh, ["pr", "list", "--repo", repo, "--state", "merged", "--limit", str(limit),
                   "--json", "number,headRefOid,mergeCommit"])
    prs = json.loads(out or "[]")
    posted = 0
    for pr in prs:
        num = int(pr["number"])
        head = (pr.get("headRefOid") or "").strip()
        if not head:
            continue
        red = failing_checks(gh, repo, head)
        if not red:
            continue
        marker = MERGED_RED_MARKER.format(head)
        if any(marker in body for body in pr_comments(gh, repo, num)):
            print(f"[auto-merge] #{num} already carries the merged-over-red alert for {head[:8]}")
            continue
        merge_oid = ((pr.get("mergeCommit") or {}).get("oid") or "").strip()
        if merge_oid:
            merge_red = failing_checks(gh, repo, merge_oid)
            if merge_red:
                counter = (f"The merge commit `{merge_oid}` is red too: {merge_red}")
            else:
                counter = (f"The merge commit `{merge_oid}` has no red check. A later re-run can look "
                           f"green while the head that was merged (`{head}`) was not.")
        else:
            counter = "GitHub did not report a merge commit for this pull request."
        text = (f"{marker}\n\n**Merged over a red head** (issue #1386). {red}\n\n{counter}")
        print(f"[auto-merge] #{num}: {red}")
        if dry:
            print(f"[auto-merge] would comment the merged-over-red alert on #{num}")
            posted += 1
            continue
        _gh(gh, ["pr", "comment", str(num), "--repo", repo, "--body", text])
        posted += 1
    print(f"[auto-merge] merged-over-red: {posted} alert(s)")
    return 0


def explain(gh: str, repo: str, pr: int, head_sha: str = "") -> int:
    """The same decision, printed for a human. Writes nothing."""
    state = pr_state(gh, repo, pr)
    fields = ("state", "isDraft", "mergeable", "mergeStateStatus", "reviewDecision", "headRefOid",
              "headRepository")
    print(f"[auto-merge] PR #{pr}: " + json.dumps({k: state.get(k) for k in fields}))
    print(f"[auto-merge] author: {((state.get('author') or {}).get('login') or 'unknown')}")
    current_head = (state.get("headRefOid") or "").strip().lower()
    verdict = bot_verdict.verdict_for_head(state.get("comments") or [], current_head)
    print(f"[auto-merge] bot verdict at this head: "
          f"{json.dumps(verdict) if verdict else 'none'}")
    judged = head_sha or (state.get("headRefOid") or "")
    red = failing_checks(gh, repo, judged)
    if red:
        print(f"[auto-merge] verdict: defers to a human — {red}")
        return 0
    reason = decide(state, head_sha, repo_owner=repo.split("/")[0])
    if reason is None:
        via = " on the bot verdict at this head (--admin: the review cannot be self-approved)" \
            if review_blocked(state) else ""
        print(f"[auto-merge] verdict: would merge PR #{pr}{via}"
              f"{' (fork head: branch kept)' if not _same_repo(state, repo) else ''}")
        return 0
    if review_blocked(state):
        print(f"[auto-merge] verdict: would approve with the owner PAT, then merge — IF the approving "
              f"account differs from the author and the author is one of {', '.join(ALLOWED_AUTHORS)} "
              f"(the job checks both at run time)")
        print(f"[auto-merge] note: {reason}")
        return 0
    print(f"[auto-merge] verdict: defers to a human — {reason}")
    return 0


def _require_token() -> None:
    """A run that cannot merge must never look like one that chose not to (issue #493).

    A `pull_request` run from a fork receives no repository secrets: `secrets.BUMP_TOKEN` was the empty
    string, so this job reported `success` while merging nothing (#481). Fail loudly instead.
    """
    import os

    token = (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()
    if not token:
        print("[auto-merge] no token: GH_TOKEN and GITHUB_TOKEN are both empty — this run cannot merge, and "
              "must not report that it decided not to (issue #493)", file=sys.stderr)
        raise SystemExit(2)


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
    m.add_argument("--actor", default="",
                   help="who triggered the CI run; authorises a bot-authored PR (owner, write collaborator, or the bot)")
    e = sub.add_parser("explain", help="print the merge verdict for a PR; writes nothing")
    e.add_argument("--repo", required=True)
    e.add_argument("--pr", type=int, required=True)
    e.add_argument("--head-sha", default="")
    e.add_argument("--gh", default="gh")
    c = sub.add_parser("red-check", help="exit 1 when the PR head has a red check; merges nothing")
    c.add_argument("--repo", required=True)
    c.add_argument("--pr", type=int, required=True)
    c.add_argument("--gh", default="gh")
    a = sub.add_parser("alert-merged-red",
                       help="comment once on a merged PR whose head pipeline was red; merges nothing")
    a.add_argument("--repo", required=True)
    a.add_argument("--limit", type=int, default=20)
    a.add_argument("--gh", default="gh")
    a.add_argument("--dry", action="store_true")
    r = sub.add_parser("recheck", help="re-evaluate the PRs whose deferral marker matches their head")
    r.add_argument("--repo", required=True)
    r.add_argument("--max-prs", type=int, default=5)
    r.add_argument("--gh", default="gh")
    r.add_argument("--dry", action="store_true")

    args = p.parse_args(argv)
    _require_token()
    if args.cmd == "red-check":
        state = pr_state(args.gh, args.repo, args.pr)
        sha = (state.get("headRefOid") or "").strip()
        red = failing_checks(args.gh, args.repo, sha)
        if red:
            print(f"[auto-merge] PR #{args.pr}: {red}", file=sys.stderr)
            return 1
        print(f"[auto-merge] PR #{args.pr}: no red check on {sha[:8]}")
        return 0
    if args.cmd == "alert-merged-red":
        return alert_merged_red(args.gh, args.repo, args.limit, args.dry)
    if args.cmd == "recheck":
        return recheck(args.gh, args.repo, args.max_prs, args.dry)
    if args.cmd == "explain":
        return explain(args.gh, args.repo, args.pr, args.head_sha)
    return run(args.gh, args.repo, args.pr, args.head_sha, args.dry,
               args.approve_when_review_required, args.actor)


if __name__ == "__main__":
    raise SystemExit(main())
