"""Route a failed CI run to a remedy: a fix or a deduped issue (issue #286).

A bot that reacts to a FAILED CI run — any run, not just a PR check — and routes it to a remedy:
repair the open PR if there is one, otherwise file ONE issue (labelled for the issue-bot) so the
failure becomes a tracked work item. Today `fix-bot` only sees open same-repo PRs and nothing
reacts to a run's conclusion.

The route decision lives HERE, in a stdlib-only, no-LLM script (unit-testable, like
`scripts/fix_bot_sweep.py`), never in a job `if:` that can silently skip (issue #107):

  * Route A — the failed run has non-empty `pull_requests` and the PR head is in THIS repo and
    pushable: dispatch the EXISTING `fix-bot` for that PR (reusing `scripts/fix_bot_sweep.py`'s
    eligibility rules; do NOT duplicate or rewrite them). A FORK-head PR must NOT be dispatched
    (the token cannot push it).
  * Route B — no pushable PR (a red main push, a red scheduled bot run, a red publish job): file
    exactly ONE issue whose title names the workflow plus the failing job, and whose body carries
    the failing job, its step, and a tail of the failing log (`gh run view RUNID --log-failed`).
    Dedupe with a body marker `<!-- run-fixer: WORKFLOW/JOB@SHORTSHA -->` (SHORTSHA = first 12
    chars of the head sha), searched with `gh issue list --search ... in:body`. If an OPEN issue
    already carries that marker, file NOTHING. Label the issue `agent:implement` so the issue-bot
    can pick it up.

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

#: How many lines of the failing log tail to carry in the issue body.
LOG_TAIL_LINES = 40


def _gh(args: list[str]) -> str:
    """One `gh` call, its stdout. Raises with the real stderr when gh fails."""
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout


def _gh_soft(args: list[str]) -> str | None:
    """`gh` output, or None when the call is refused — a read that fails must not crash the run."""
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return r.stdout


def marker(workflow: str, job: str, head_sha: str) -> str:
    """The dedupe marker for one workflow/job@head-sha: the memory a later run reads."""
    short = (head_sha or "")[:12]
    return f"<!-- {MARKER_PREFIX} {workflow}/{job}@{short} -->"


def run_pull_requests(repo: str, run_id: int) -> list[dict]:
    """The PR(s) this run reports on, from the REST run object's `pull_requests` array.

    `gh run view --json` rejects a `pullRequests` field outright (measured, #277), so the PRs come
    from the REST endpoint. A fork-PR run's array is EMPTY here (measured, #277/#170) — which is
    exactly the shape this reactor must not dispatch — so a fork PR is never routed to the fix-bot.
    """
    data = json.loads(_gh(["api", f"/repos/{repo}/actions/runs/{run_id}"]) or "{}")
    return data.get("pull_requests") or []


def run_detail(repo: str, run_id: int) -> dict:
    """The run's conclusion, head sha, event, workflow name and jobs (one `gh run view`)."""
    out = _gh(["run", "view", str(run_id), "--repo", repo,
               "--json", "conclusion,headSha,event,workflowName,displayTitle,jobs"])
    return json.loads(out or "{}")


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
    """Dispatch the EXISTING fix-bot for this PR (the same argv the sweep uses)."""
    r = subprocess.run(["gh", "workflow", "run", "fix-bot.yml", "--repo", repo,
                        "-f", f"pr_number={pr['number']}", "-f", f"branch={pr['headRefName']}",
                        "-f", f"check={check}", "-f", "rounds=3"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"dispatch failed: {r.stderr.strip()}")


def _pr_from_run(repo: str, run: dict, run_id: int) -> dict | None:
    """The pushable same-repo PR this run reports on, or None.

    Reuses `fix_bot_sweep`'s eligibility rules (open, non-draft, head in THIS repo, not `main`,
    at least one failing check, fewer than the attempt cap) — never duplicates them. A fork PR
    (head owner != repo owner) is refused here, exactly as the sweep refuses it.
    """
    prs = run_pull_requests(repo, run_id)
    if not prs:
        return None
    # The REST `pull_requests` array carries number + head ref + head repo; map to the shape the
    # sweep's `eligible` expects.
    for p in prs:
        head = p.get("head") or {}
        head_repo = head.get("repo") or {}
        owner = (head_repo.get("owner") or {}).get("login") or ""
        repo_owner = repo.split("/")[0]
        if owner and owner.lower() != repo_owner.lower():
            print(f"[run-fixer] run {run_id} reports on a FORK PR (head owner {owner}): "
                  f"the token cannot push it - leaving it to a human", flush=True)
            continue
        pr = {"number": p.get("number"), "headRefName": head.get("ref"),
              "headRepositoryOwner": {"login": owner or repo_owner},
              "isDraft": False, "title": p.get("title") or f"PR {p.get('number')}",
              "updatedAt": ""}
        ok, why = fix_bot_sweep.eligible(repo, pr)
        if ok:
            return pr
        print(f"[run-fixer] run {run_id} PR #{pr['number']} not eligible: {why}", flush=True)
    return None


def issue_body(run: dict, job: dict, log_tail: str, marker: str) -> str:
    """The issue body: the failing job, its step, the log tail, and the dedupe marker."""
    step = ""
    for s in (job.get("steps") or []):
        if (s.get("conclusion") or "").lower() in ("failure", "cancelled", "timed_out"):
            step = s.get("name") or ""
            break
    lines = [
        f"A CI run failed and no open same-repo PR can be repaired for it, so this issue tracks "
        f"the failure as a work item for the issue-bot.",
        "",
        f"- **workflow:** `{run.get('workflowName') or '?'}`",
        f"- **run:** `{run.get('displayTitle') or '?'}`",
        f"- **event:** `{run.get('event') or '?'}`",
        f"- **head sha:** `{(run.get('headSha') or '')[:12]}`",
        f"- **failing job:** `{job.get('name') or '?'}`",
        f"- **failing step:** `{step or '(none named)'}`",
        "",
        "Failing log tail:",
        "",
        "```",
        log_tail,
        "```",
        "",
        "Filed by the run-failure reactor (`scripts/run_failure_reactor.py`). The issue-bot owns "
        "the implementation; the fix-bot owns PR repair. Nothing was changed by the run that "
        "filed this.",
        "",
        marker,
    ]
    return "\n".join(lines)


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


def route(repo: str, run_id: int, check: str = "make ci-unit", dry: bool = False) -> int:
    """Route one completed failed run to a remedy. Returns the exit code."""
    run = run_detail(repo, run_id)
    conclusion = (run.get("conclusion") or "").lower()
    if conclusion != "failure":
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
    pr = _pr_from_run(repo, run, run_id)
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

    # Route B: no pushable PR -> file ONE deduped issue.
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
