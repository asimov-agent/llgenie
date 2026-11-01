"""Route a failed CI run to a remedy: a fix or a deduped issue (issue #286).

A bot that reacts to a FAILED CI run — any run, not just a PR check — and routes it to a remedy:
repair the open PR if there is one, otherwise file ONE issue (labelled for the issue-bot) so the
failure becomes a tracked work item. Today `fix-bot` only sees open same-repo PRs and nothing
reacts to a run's conclusion.

The route decision lives HERE, in a stdlib-only, no-LLM script (unit-testable, like
`scripts/fix_bot_sweep.py`), never in a job `if:` that can silently skip (issue #107):

  * Route A — the failed run reports a PR this bot can PUSH: dispatch the EXISTING `fix-bot` for
    that PR (reusing `scripts/fix_bot_sweep.py`'s eligibility rules; do NOT duplicate or rewrite
    them). Pushable means this repository OR the owner's fork (`TRUSTED_FORK`), which is where every
    agent PR lives — and a fork `pull_request` run's REST `pull_requests` array is EMPTY (measured,
    #277/#170), so the PR is resolved from the run's `head_branch` + `head_repository.owner.login`
    (`scripts/resolve_run_pr.py`, the resolver auto-merge uses). A FIFTH-PARTY fork is still refused:
    no token we hold can push it (issue #555).
  * The dispatch must carry the OWNER identity. The dispatched run's actor is the token's identity,
    and every guarded bot refuses `github-actions[bot]` (#510) — with `github.token` the dispatched
    fix-bot died in its own guard (run `39917926028`). So `gh workflow run` uses `DISPATCH_TOKEN`
    from the environment, never argv, and a missing one is a LOUD failure (issue #555).
  * Route B — no pushable PR (a red main push, a red scheduled bot run, a red publish job): file
    exactly ONE issue whose title names the workflow plus the failing job, and whose body carries
    the failing job, its step, and a tail of the failing log (`gh run view RUNID --log-failed`).
    Dedupe with a body marker `<!-- run-fixer: WORKFLOW/JOB@SHORTSHA -->` (SHORTSHA = first 12
    chars of the head sha), searched with `gh issue list --search ... in:body`. If an OPEN issue
    already carries that marker, file NOTHING. Label the issue `agent:implement` so the issue-bot
    can pick it up.
  * Route B files only WORK THAT IS STILL WORK (issue #565). "No pushable PR" covers two very
    different states, and only one of them is a work item:
      - the PR is OPEN but not pushable right now (a draft, or its repair attempts are spent) -
        the failure is live, so it is filed;
      - no OPEN PR exists for the head at all (merged, closed, branch deleted), or a push run on a
        branch that a LATER run of the same workflow already turned green - the failure is history,
        and filing it hands the implementer a defect fixed before the issue existed.
    Measured on 2026-10-23: all six open `agent:implement` issues this reactor had filed were the
    second state, and the issue-bot's 3/day budget made them two days of wasted runs. The verdict is
    printed (`is SUPERSEDED: <reason> - filing nothing`), never a silent skip.

The reactor is a WRITER (it files issues / dispatches fix-bot), so it joins the claim protocol in
`scripts/bot_claims.py` (issues #279/#285): it consults claims before acting and writes its own
claim on the subject it takes, exactly like the other bots do.

It NEVER repairs, commits, pushes or merges in the Route B path — it only files. The issue-bot
owns implementation, fix-bot owns PR repair. One code path per resource; no second implementation
of another bot's logic.

A run it cannot diagnose is reported LOUDLY, never silently dropped: a `gh` read that fails, or
a run shape it does not recognise, goes to stderr and the exit code is non-zero.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bot_claims  # the shared protocol (issue #279)
import fix_bot_sweep  # the eligibility rules we REUSE, never duplicate (issue #222)
from issue_body import render as render_body  # the one issue shape (issue #745); the local
#   ``issue_body()`` below keeps its published name, so the renderer is imported under another one
import resolve_run_pr  # the run -> PR resolver auto-merge uses (#509), reused, never rewritten

#: This bot, as the claim marker names it (scripts/bot_claims.py). The name is the workflow's bot
#: name (`run-failure-reactor.yml` -> `run-failure-reactor`) so a claim reads as the thing a
#: maintainer sees in the Actions tab.
RUN_FIXER = "run-failure-reactor"

#: The reactor's own workflow name. A `workflow_run` event fires for EVERY completed run in the
#: repo, including the reactor's own — so the reactor must skip its own runs or it re-triggers
#: itself forever. The name is matched as a substring so a renamed display name still skips.
OWN_WORKFLOW = "run-failure-reactor"

#: The label the filed issue carries so the issue-bot picks it up (scripts/issue_implementer.py
#: picks `agent:implement` first).
IMPLEMENT_LABEL = "agent:implement"

#: The dedupe marker prefix. The full marker is `<!-- run-fixer: WORKFLOW/JOB@SHORTSHA -->`.
MARKER_PREFIX = "run-fixer:"

#: The fork owner whose PRs this bot may push: every agent PR is pushed there, and the fix-bot's
#: own sweep repairs it (`fix_bot_sweep.eligible(..., own_fork=...)`, issue #477).
TRUSTED_FORK = "andyholst"

#: The credential `gh workflow run` carries. The dispatched run's actor is the token's identity, and
#: every guarded workflow of this repo refuses `github-actions[bot]` (#510) — so the dispatch needs
#: the OWNER, by env var name only, never on argv (issue #555).
DISPATCH_TOKEN_ENV = "DISPATCH_TOKEN"

#: How many lines of the failing log tail to carry in the issue body.
LOG_TAIL_LINES = 40

#: The conclusion of a LATER run on the same branch that proves an earlier failure is no longer live
#: (issue #565). Anything else (a later failure, a cancellation) leaves the failure standing.
SUPERSEDING_CONCLUSION = "success"

#: How many of a branch's newest runs to read when deciding whether a failure was superseded.
SUPERSEDE_SCAN = 10


def _gh(args: list[str]) -> str:
    """One `gh` call, its stdout. Raises with the real stderr when gh fails."""
    r = subprocess.run(["gh", *args], capture_output=True, text=True)  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
    if r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout


def _gh_soft(args: list[str]) -> str | None:
    """`gh` output, or None when the call is refused — a read that fails must not crash the run."""
    r = subprocess.run(["gh", *args], capture_output=True, text=True)  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
    if r.returncode != 0:
        return None
    return r.stdout


def marker(workflow: str, job: str, head_sha: str) -> str:
    """The dedupe marker for one workflow/job@head-sha: the memory a later run reads."""
    short = (head_sha or "")[:12]
    return f"<!-- {MARKER_PREFIX} {workflow}/{job}@{short} -->"


def run_rest(repo: str, run_id: int) -> dict:
    """The REST run object: `pull_requests`, `head_branch`, `head_repository`, `event`.

    `gh run view --json` rejects a `pullRequests` field outright (measured, #277), so the PRs come
    from the REST endpoint — and a fork-PR run's array is EMPTY there (measured, #277/#170), which
    is why the head branch + head repository are read from the same object (issue #555).
    """
    return json.loads(_gh(["api", f"/repos/{repo}/actions/runs/{run_id}"]) or "{}")


def run_pull_requests(repo: str, run_id: int) -> list[dict]:
    """The PR(s) the REST run object names. Empty for a fork `pull_request` run (#277/#170)."""
    return run_rest(repo, run_id).get("pull_requests") or []


def run_detail(repo: str, run_id: int) -> dict:
    """The run's conclusion, head sha, event, workflow name, creation time and jobs (one `gh run view`).

    `createdAt` is what orders this run against the branch's newer ones, which is how a superseded
    failure is recognised (issue #565).
    """
    out = _gh(["run", "view", str(run_id), "--repo", repo,
               "--json", "conclusion,headSha,event,workflowName,displayTitle,createdAt,jobs"])
    return json.loads(out or "{}")


def open_pr_exists(repo: str, branch: str) -> "bool | None":
    """Whether ANY open PR has this head branch, whatever repository owns it.

    Deliberately unfiltered: `resolve_run_pr.open_pr_for_head` narrows by owner for the push decision,
    and that narrowing would make a stranger's live PR look absent here (issue #565). Returns None
    when the read failed — an unreadable answer is UNKNOWN, never "no open PR".
    """
    out = _gh_soft(["pr", "list", "--repo", repo, "--state", "open", "--search",
                    f"head:{branch}", "--limit", "20", "--json", "number", "--jq", ".[].number"])
    if out is None:
        return None
    return bool(out.strip())


def superseded(repo: str, run: dict, rest: dict) -> str | None:
    """Why this failure is no longer work to do, or None while it still is (issue #565).

    Route B files a work item for "a failed run with no PR this bot can repair". Two very different
    states land there, and only one is work:

      * a PR that is OPEN but not pushable right now - a draft, or its repair attempts are spent:
        the failure is live, so it is filed;
      * NO OPEN PR for the head at all - merged, closed, branch deleted - or a push run on a branch
        that a LATER run of the same workflow already turned green: the failure is history.

    An unreadable answer is UNKNOWN, never "superseded": a failed read must not drop a real failure.
    """
    event = (run.get("event") or "").lower()
    branch = rest.get("head_branch") or ""

    if event == "pull_request":
        if not branch:
            return None
        repo_owner = repo.split("/")[0]
        owner = (((rest.get("head_repository") or {}).get("owner") or {}).get("login")
                 or repo_owner)
        if owner.lower() not in (repo_owner.lower(), TRUSTED_FORK.lower()):
            # A fifth-party fork: no token this repository holds can read or push it, so its PR
            # state is UNKNOWN here. Route B has already reported it; an unknown never supersedes.
            return None
        # An OPEN PR for this head, whoever owns it. A merged/closed PR and a deleted branch both
        # answer "none", which is the only thing this check may conclude from absence.
        exists = open_pr_exists(repo, branch)
        if exists is None:
            print(f"[run-fixer] the open-PR state of `{branch}` could not be read - not declaring "
                  f"this failure superseded on an unknown", flush=True)
            return None
        if not exists:
            return (f"the PR it ran on (head `{owner}:{branch}`) is merged or closed - no branch is "
                    f"left to repair")
        return None

    if event != "push" or not branch:
        return None
    workflow = run.get("workflowName") or ""
    if not workflow:
        return None
    out = _gh_soft(["run", "list", "--repo", repo, "--branch", branch, "--workflow", workflow,
                    "--limit", str(SUPERSEDE_SCAN), "--json", "databaseId,conclusion,createdAt"])
    if out is None:
        print(f"[run-fixer] the run list for `{branch}` could not be read - not declaring this "
              f"failure superseded on an unknown", flush=True)
        return None
    mine = run.get("createdAt") or ""
    for row in json.loads(out or "[]"):
        if (row.get("conclusion") or "").lower() != SUPERSEDING_CONCLUSION:
            continue
        later = row.get("createdAt") or ""
        # Without this run's own timestamp the order is unknown; an unknown is not a supersede.
        if not mine or not later or later <= mine:
            continue
        return f"a later run of {workflow} on `{branch}` succeeded at {later}"
    return None


def failing_jobs(run: dict) -> list[dict]:
    """The jobs of a failed run whose conclusion is `failure` (or `cancelled`/`timed_out`)."""
    jobs = run.get("jobs") or []
    return [j for j in jobs if (j.get("conclusion") or "").lower() in
            ("failure", "cancelled", "timed_out")]


def failing_log_tail(repo: str, run_id: int, job_id: int | None) -> str:
    """A tail of the failing log for one job, or a loud note when it cannot be read."""
    if not job_id:
        return "(no job id to read a log for)"
    out = _gh_soft(["run", "view", str(run_id), "--repo", repo, "--log-failed",
                    "--job", str(job_id)])
    if out is None:
        return "(the failing log could not be read)"
    lines = [l for l in out.splitlines() if l.strip()]
    return "\n".join(lines[-LOG_TAIL_LINES:])


def _pr_comments(repo: str, pr: int) -> list[dict]:
    """The PR's comments — where the claim protocol lives (scripts/bot_claims.py)."""
    out = _gh(["pr", "view", str(pr), "--repo", repo, "--json", "comments"])
    return (json.loads(out or "{}") or {}).get("comments") or []


def _run_is_live(repo: str, run_id: int) -> "bool | None":
    """Whether the run that posted a claim is still going (cached, scripts/bot_claims.py #291)."""
    return bot_claims.run_is_live(lambda args: _gh(args), run_id)


def occupied_pr(repo: str, pr: dict) -> str | None:
    """A reason to leave this PR alone, or None: the claim protocol (issue #279)."""
    comments = _pr_comments(repo, pr["number"])
    # PR_CLAIM_TTL, not the default: that is the FALLBACK for a marker written before #292, which
    # carries its own ttl. A repair can run 180 minutes, so a claim younger than that is a bot
    # still working, not a stale one (scripts/bot_claims.py).
    why = bot_claims.occupied(comments, RUN_FIXER, ttl=bot_claims.PR_CLAIM_TTL,
                              is_live=lambda rid: _run_is_live(repo, rid))
    if why:
        return why
    gone = bot_claims.released(comments, RUN_FIXER, ttl=bot_claims.PR_CLAIM_TTL,
                               is_live=lambda rid: _run_is_live(repo, rid))
    if gone:
        # #291: say it out loud - the PR is free because its holder is GONE, not because it idled.
        print(f"[run-fixer] #{pr['number']}: {gone}", flush=True)
    return None


def claim_pr(repo: str, pr: dict) -> None:
    """Say we are starting, on the PR, before the dispatch - in the marker the other bots read."""
    _gh(["pr", "comment", str(pr["number"]), "--repo", repo, "--body",
         bot_claims.claim_comment(RUN_FIXER, "fix", dt.datetime.now(dt.timezone.utc),
                                  ttl=bot_claims.PR_CLAIM_TTL,
                                  run_id=os.environ.get("GITHUB_RUN_ID"))])


def dispatch_fix_bot(repo: str, pr: dict, check: str = "make ci-unit") -> None:
    """Dispatch the EXISTING fix-bot for this PR, as the OWNER (issue #555).

    The dispatched run's actor IS the identity of the token `gh` carries, and every guarded workflow
    of this repo refuses `github-actions[bot]` — a dispatch with `github.token` produced a fix-bot run
    that died in its own guard (measured: run `39917926028`). So the dispatch takes its credential
    from the environment (`DISPATCH_TOKEN`), never from argv, and a missing one fails LOUDLY instead
    of producing a red no-op run we would then file an issue about.
    """
    token = (os.environ.get(DISPATCH_TOKEN_ENV) or "").strip()
    if not token:
        raise RuntimeError(
            f"{DISPATCH_TOKEN_ENV} is empty: a dispatch with the job token makes the fix-bot run's "
            f"actor `github-actions[bot]`, which its own guard refuses (issue #555). Nothing was "
            f"dispatched for PR #{pr.get('number')}.")
    r = subprocess.run(["gh", "workflow", "run", "fix-bot.yml", "--repo", repo,  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
                        "-f", f"pr_number={pr['number']}", "-f", f"branch={pr['headRefName']}",
                        "-f", f"check={check}", "-f", "rounds=3"],
                       capture_output=True, text=True, env=dict(os.environ, GH_TOKEN=token))
    if r.returncode != 0:
        raise RuntimeError(f"dispatch failed: {r.stderr.strip()}")


def _fork_pr(repo: str, rest: dict, run_id: int) -> dict | None:
    """The open PR a FORK run reports on, or None (issue #555).

    A fork `pull_request` run's REST `pull_requests` array is empty (#277/#170), so the PR is
    resolved from the run's own head branch + head repository owner — the resolver auto-merge uses
    (`scripts/resolve_run_pr.py`). Only the owner's fork is pushable here; a fifth-party fork cannot
    be pushed by any token this repository holds, so it is reported and left to a human.
    """
    branch = rest.get("head_branch") or ""
    owner = ((rest.get("head_repository") or {}).get("owner") or {}).get("login") or ""
    if not branch or not owner:
        return None
    if owner.lower() != TRUSTED_FORK:
        print(f"[run-fixer] run {run_id} is a FIFTH-PARTY fork PR (head owner {owner}): not ours "
              f"to push - leaving it to a human", flush=True)
        return None
    number = resolve_run_pr.open_pr_for_head(repo, owner, branch)
    if number is None:
        print(f"[run-fixer] run {run_id} reports no OPEN PR for {owner}:{branch} - nothing to "
              f"repair", flush=True)
        return None
    out = _gh(["pr", "view", str(number), "--repo", repo, "--json",
               "number,title,headRefName,headRepositoryOwner,isDraft,state,updatedAt"])
    detail = json.loads(out or "{}") or {}
    if (detail.get("state") or "").upper() != "OPEN":
        print(f"[run-fixer] PR #{number} is {detail.get('state') or '?'}: nothing to repair",
              flush=True)
        return None
    return {"number": detail.get("number") or number,
            "headRefName": detail.get("headRefName") or branch,
            "headRepositoryOwner": detail.get("headRepositoryOwner") or {"login": owner},
            "isDraft": bool(detail.get("isDraft")),
            "title": detail.get("title") or f"PR {number}",
            "updatedAt": detail.get("updatedAt") or ""}


def _pr_from_run(repo: str, run: dict, run_id: int, rest: dict | None = None) -> dict | None:
    """The PR this run reports on that this bot can PUSH, or None.

    Reuses `fix_bot_sweep`'s eligibility rules (open, non-draft, pushable head, not `main`, at least
    one failing check, fewer than the attempt cap) — never duplicates them. Two sources, because a
    fork run reports no PR at all:

      * the REST `pull_requests` array (a same-repo PR);
      * for an EMPTY array, the run's head branch + head owner (`_fork_pr`): the owner's fork is
        pushable (`own_fork=`), a fifth-party fork is not (issue #555).

    `rest` is the run object `route()` already read, so the same API answer is not fetched twice and
    the superseded decision (#565) sees exactly what the routing decision saw.
    """
    rest = rest if rest is not None else run_rest(repo, run_id)
    repo_owner = repo.split("/")[0]
    candidates: list[dict] = []
    for p in rest.get("pull_requests") or []:
        head = p.get("head") or {}
        owner = ((head.get("repo") or {}).get("owner") or {}).get("login") or ""
        if owner and owner.lower() != repo_owner.lower():
            print(f"[run-fixer] run {run_id} reports on a FORK PR (head owner {owner}): not ours "
                  f"to push - leaving it to a human", flush=True)
            continue
        candidates.append({"number": p.get("number"), "headRefName": head.get("ref"),
                           "headRepositoryOwner": {"login": owner or repo_owner},
                           "isDraft": False, "title": p.get("title") or f"PR {p.get('number')}",
                           "updatedAt": ""})
    if not candidates:
        fork_pr = _fork_pr(repo, rest, run_id)
        if fork_pr:
            candidates.append(fork_pr)
    for pr in candidates:
        ok, why = fix_bot_sweep.eligible(repo, pr, own_fork=TRUSTED_FORK)
        if ok:
            return pr
        print(f"[run-fixer] run {run_id} PR #{pr['number']} not eligible: {why}", flush=True)
    return None


def issue_body(run: dict, job: dict, log_tail: str, marker: str) -> str:
    """The issue body: the shape every issue in this repository carries (issue #745)."""
    step = ""
    for s in (job.get("steps") or []):
        if (s.get("conclusion") or "").lower() in ("failure", "cancelled", "timed_out"):
            step = s.get("name") or ""
            break
    workflow = run.get("workflowName") or "?"
    job_name = job.get("name") or "?"
    return render_body(
        marker=marker,
        problem=(
            f"The `{workflow}` run `{run.get('displayTitle') or '?'}` (event "
            f"`{run.get('event') or '?'}`, head `{(run.get('headSha') or '')[:12]}`) failed in job "
            f"`{job_name}`, step `{step or '(none named)'}`, and no pull request this bot can repair "
            "was found for it."
        ),
        why=(
            "A failed run that no bot repairs and nobody tracks is work that quietly stops being "
            "done: `main` stays red, or a bot's scheduled job stops producing its artifact, and the "
            "next reader has to reconstruct the failure from a log that has since expired."
        ),
        how=[
            "Read the failing log tail in `## Technical` and reproduce the failure with the make "
            "target that step ran (`make <target>`), never by re-running the workflow blind.",
            "Fix the cause in the repository, so the gate is green for the next run instead of this "
            "one being retried.",
            "Reference this issue from the PR (`closes #<n>`) so the failure and its fix stay one "
            "work item.",
        ],
        benefit=(
            "Every failed run has an owner and a work item: the failure is reproduced from its own "
            "log instead of guessed at, and the class of failure is fixed rather than re-run."
        ),
        acceptance=[
            "the failing make target is green locally on this host, with its real output recorded",
            "the PR that fixes it is green in CI on the same job that failed",
            "`closes #<this issue>` is in that PR, so merging it closes the failure",
        ],
        technical=[
            f"**workflow:** `{workflow}`",
            f"**run:** `{run.get('displayTitle') or '?'}`",
            f"**event:** `{run.get('event') or '?'}`",
            f"**head sha:** `{(run.get('headSha') or '')[:12]}`",
            f"**failing job:** `{job_name}`",
            f"**failing step:** `{step or '(none named)'}`",
            "Failing log tail (`gh run view <id> --log-failed`):",
            "",
            "```",
            log_tail,
            "```",
            "",
            "Filed by the run-failure reactor (`scripts/run_failure_reactor.py`). The issue-bot owns "
            "the implementation; the fix-bot owns PR repair. Nothing was changed by the run that "
            "filed this. The marker on line 1 is the dedupe key (`workflow/job@sha`).",
        ],
    )


def filed(repo: str, marker: str) -> bool:
    """Has this workflow/job@head-sha been filed already? The marker is the memory."""
    out = _gh(["issue", "list", "--repo", repo, "--state", "open", "--search",
               f"\"{marker}\" in:body", "--limit", "5", "--json", "number"])
    return bool(json.loads(out or "[]") or [])


def file_issue(repo: str, run: dict, job: dict, log_tail: str, marker: str,
               dry: bool = False) -> str | None:
    """File ONE issue for this failure; return its URL, or None when already filed / dry."""
    if filed(repo, marker):
        print(f"[run-fixer] already filed: {marker}", flush=True)
        return None
    title = f"ci: {run.get('workflowName') or '?'} / {job.get('name') or '?'} failed"
    if dry:
        print(f"[run-fixer] would file: {title} ({marker})", flush=True)
        return None
    out = _gh(["issue", "create", "--repo", repo, "--title", title,
               "--body", issue_body(run, job, log_tail, marker),
               "--label", IMPLEMENT_LABEL])
    print(f"[run-fixer] filed: {out.strip()}", flush=True)
    return out.strip()


def later_run_of_the_same_workflow(repo: str, run: dict) -> str | None:
    """The createdAt of the LATEST later run of this workflow on this branch (None when none is seen).

    A cancelled run is not an answer (#843): if a later run of the same workflow exists on the branch,
    the cancellation was a supersede and there is nothing to do; if none exists, the run was killed
    with its verdict still owed, and the log must say so instead of "not a failure, nothing to do".
    An unreadable listing returns None — an unknown never becomes a decision.
    """
    workflow = run.get("workflowName") or ""
    branch = run.get("head_branch") or (run_rest(repo, run.get("databaseId") or 0).get("head_branch") or "")
    if not workflow or not branch:
        return None
    out = _gh_soft(["run", "list", "--repo", repo, "--branch", branch, "--workflow", workflow,
                    "--limit", str(SUPERSEDE_SCAN), "--json", "databaseId,conclusion,createdAt"])
    if out is None:
        return None
    mine = run.get("createdAt") or ""
    later = [row.get("createdAt") or "" for row in json.loads(out or "[]")
             if (row.get("createdAt") or "") > mine]
    return max(later) if later else None


def route(repo: str, run_id: int, check: str = "make ci-unit", dry: bool = False) -> int:
    """Route one completed failed run to a remedy. Returns the exit code."""
    run = run_detail(repo, run_id)
    conclusion = (run.get("conclusion") or "").lower()
    if conclusion != "failure":
        if conclusion == "cancelled":
            # A cancellation is not a verdict (#843): the run was killed, and whether it still owes
            # one depends on whether a later run of the same workflow took over.
            later = later_run_of_the_same_workflow(repo, {**run, "databaseId": run_id})
            if later:
                print(f"[run-fixer] run {run_id} was cancelled and a later run of "
                      f"`{run.get('workflowName') or '?'}` took over at {later} - superseded, "
                      f"nothing to do", flush=True)
            else:
                print(f"[run-fixer] run {run_id} was CANCELLED with no later run of "
                      f"`{run.get('workflowName') or '?'}` on its branch - that is PENDING, not a "
                      f"verdict: `make ci-requeue-cancelled` re-runs it (issue #843)", flush=True)
            return 0
        print(f"[run-fixer] run {run_id} conclusion is `{conclusion or '?'}` - not a failure, "
              f"nothing to do", flush=True)
        return 0
    if OWN_WORKFLOW in (run.get("workflowName") or ""):
        # A `workflow_run` event fires for the reactor's own completion too; skip it or the
        # reactor re-triggers itself forever.
        print(f"[run-fixer] run {run_id} is the reactor's own workflow - skipping to avoid "
              f"re-triggering itself", flush=True)
        return 0

    # Route A: a pushable same-repo PR -> claim + dispatch the existing fix-bot.
    rest = run_rest(repo, run_id)
    pr = _pr_from_run(repo, run, run_id, rest)
    if pr is not None:
        why = occupied_pr(repo, pr)
        if why:
            print(f"[run-fixer] run {run_id} PR #{pr['number']} is {why}: leaving it to that bot",
                  flush=True)
            return 0
        if not dry:
            claim_pr(repo, pr)
            dispatch_fix_bot(repo, pr, check)
        print(f"[run-fixer] run {run_id} -> dispatched the fix-bot for #{pr['number']}",
              flush=True)
        return 0

    # Route B: no pushable PR -> file ONE deduped issue, but only for a failure that is still work
    # (issue #565). A merged PR's run, or a push a later run already turned green, is history: filing
    # it hands the implementer a defect that was fixed before the issue was written.
    why = superseded(repo, run, rest)
    if why:
        print(f"[run-fixer] run {run_id} is SUPERSEDED: {why} - filing nothing", flush=True)
        return 0

    jobs = failing_jobs(run)
    if not jobs:
        # A failed run with no failing job is a startup refusal (issue #330): the run's `name` is
        # the file PATH and there is no log. Report it loudly - it is a workflow file GitHub
        # refused, not a regression in the code the run would have tested.
        print(f"[run-fixer] run {run_id} failed with no failing job (a 0-job red run whose name "
              f"is the file path is a startup refusal, issue #330) - reporting loudly",
              file=sys.stderr, flush=True)
        return 1
    job = jobs[0]
    log_tail = failing_log_tail(repo, run_id, job.get("databaseId"))
    m = marker(run.get("workflowName") or "?", job.get("name") or "?", run.get("headSha") or "")
    file_issue(repo, run, job, log_tail, m, dry=dry)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True, help="owner/name")
    ap.add_argument("--run-id", required=True, type=int, help="the completed run to route")
    ap.add_argument("--check", default="make ci-unit", help="the check the fix-bot drives")
    ap.add_argument("--dry", action="store_true", help="decide and print; dispatch/file nothing")
    a = ap.parse_args(argv)
    try:
        return route(a.repo, a.run_id, a.check, a.dry)
    except RuntimeError as err:
        # A crashed decision is never "nothing to do" (issue #312): report it loudly.
        print(f"[run-fixer] {err}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
