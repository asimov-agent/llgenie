"""Report jobs that have been queued far too long, so a stuck runner is loud (issues #254, #294).

When a runner label matches nothing (an offline self-hosted runner, or hosted macOS minutes
exhausted), GitHub does not fail the job — it leaves it `queued` forever. The run never
concludes, `mergeStateStatus` stays BLOCKED, and every PR's checks sit at "pending" with no
signal anywhere that anything is wrong. This makes that state loud:

  * list the in-progress runs of a repo, then the jobs still `queued`,
  * flag the ones queued longer than `--minutes` (default 30),
  * print a table that names the runner label and the age, and
  * `--comment` DELIVERS the report where a human will read it — on the pull request the run
    reports on (the issues-comments endpoint is the one API that covers a PR too), or, for a run
    no PR tracks (a schedule/push run), as ONE issue per stuck runner label, deduplicated by a
    marker in its body. `--dry` prints what it WOULD post and posts nothing.

A workflow RUN ID is not an issue number: posting to `/repos/{repo}/issues/{run_id}/comments`
404s, and an alarm whose report is written nowhere is worse than no alarm (that was #294, found by
running it live). So every delivery is checked, and a delivery that fails is LOUD: the failures go
to stderr and the exit code says the report did not land.

also prints a RUN-LEVEL ghost-queue squat report (issue #2656): orphan-queued runs (no open PR, head
branch deleted) and runs stuck `in_progress` whose job records have all concluded (job expiry, #1889,
read as expiry, never a live matrix). The squat is reported ONCE PER EPISODE (a deduped issue keyed on
the run-id set) and is never cancelled by this alarm — cancellation is the owner's explicit word.

Exit codes: 0 = nothing stuck and no squat, 1 = at least one job is stuck or a ghost-run squat (so a
scheduled job goes red), 2 = the GitHub read failed, 3 = stuck/squat found AND the report could not be
delivered.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import issue_body  # noqa: E402  (the one issue shape, #745)

MARKER = "queued-run-alarm"


def _gh(args: list[str]) -> str:
    r = subprocess.run(["gh", *args], capture_output=True, text=True)  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
    if r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout


def _job_detail(repo: str, job_id: int | None) -> dict:
    """The job's own REST object (labels, runner_name) — `{}` when unavailable.

    `gh run view --json jobs` can leave `labels` empty for a queued job (observed live), and the
    label is what tells a maintainer WHICH runner is missing. Never fatal: an alarm that cannot
    fetch a detail still reports the job.
    """
    if not job_id:
        return {}
    try:
        return json.loads(_gh(["api", f"/repos/{repo}/actions/jobs/{job_id}"]) or "{}")
    except (RuntimeError, ValueError):
        return {}


def _age_minutes(started: str | None, now: dt.datetime) -> float | None:
    """Minutes since a job's `started_at` (which GitHub sets when it is queued)."""
    if not started:
        return None
    try:
        t = dt.datetime.strptime(started, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None
    return round((now - t).total_seconds() / 60.0, 1)


def stuck_jobs(repo: str, minutes: float = 30.0, now: dt.datetime | None = None,
               limit: int = 30) -> list[dict]:
    """Jobs queued longer than `minutes` in this repo's in-progress runs."""
    now = now or dt.datetime.now(dt.timezone.utc)
    # BOTH statuses: a run whose jobs are all queued reports `queued`, not `in_progress` — the
    # exact case this alarm exists for, and the one an in_progress-only query misses.
    runs: list[dict] = []
    seen: set[int] = set()
    for status in ("queued", "in_progress"):
        for run in json.loads(_gh(["run", "list", "--repo", repo, "--status", status,
                                   "--limit", str(limit),
                                   "--json", "databaseId,workflowName,headBranch,url"]) or "[]"):
            if run.get("databaseId") not in seen:
                seen.add(run.get("databaseId"))
                runs.append(run)
    out: list[dict] = []
    for run in runs:
        jobs = json.loads(_gh(["run", "view", str(run["databaseId"]), "--repo", repo,
                               "--json", "jobs"]) or "{}").get("jobs") or []
        for job in jobs:
            if (job.get("status") or "") != "queued":
                continue
            age = _age_minutes(job.get("startedAt"), now)
            if age is None or age < minutes:
                continue
            labels = list(job.get("labels") or [])
            runner = job.get("runnerName") or job.get("runner_name") or ""
            if not labels or not runner:
                # `gh run view --json jobs` can leave `labels` empty (seen live), and the label
                # is the single most useful fact here: it decides which runner is missing. Pull
                # it from the job's own REST object when the list did not carry it.
                detail = _job_detail(repo, job.get("databaseId"))
                labels = labels or list(detail.get("labels") or [])
                runner = runner or detail.get("runner_name") or ""
            out.append({"run": run["databaseId"], "run_url": run.get("url", ""),
                        "workflow": run.get("workflowName", ""), "branch": run.get("headBranch", ""),
                        "job": job.get("name", ""), "labels": ",".join(labels),
                        "runner": runner, "minutes": age})
    return sorted(out, key=lambda j: -j["minutes"])


def render(rows: list[dict], minutes: float) -> str:
    """The report a human reads: what, how long, and which label is not being picked up."""
    if not rows:
        return f"no job has been queued longer than {minutes:.0f} minutes"
    lines = [f"{len(rows)} job(s) queued longer than {minutes:.0f} minutes:", ""]
    for r in rows:
        runner = f"  runner={r['runner']}" if r.get("runner") else ""
        lines.append(f"  {r['minutes']:6.1f} min  {r['workflow']} / {r['job']}  "
                     f"labels=[{r['labels']}]  branch={r['branch']}  run={r['run']}{runner}")
    labels = sorted({r["labels"] for r in rows})
    lines += ["", "A job stuck in `queued` with no runner means no machine matches those "
                  f"labels ({', '.join(labels)}): a self-hosted runner is offline/unregistered, or "
                  "the account's hosted-runner minutes/spending limit for that OS is exhausted.",
              "GitHub does not fail such a job, so the run never concludes and every PR's checks "
              "stay pending — see issue #254."]
    return "\n".join(lines)


def render_squat(orphans: list[dict], expired: list[dict], minutes: float) -> str:
    """The run-level ghost-queue squat report: run ids and the orphan / live / expired split.

    A permanently `in_progress` run whose jobs have all concluded is READ AS JOB EXPIRY (#1889
    wording): its verdict is expired, not a live matrix, and it never counts toward the live
    queued/in_progress supply.
    """
    if not orphans and not expired:
        return (f"no ghost-run squat: no orphan-queued run and no expired in_progress run "
                f"past {minutes:.0f} minutes")
    lines = ["", "GHOST-RUN SQUAT (run-level, issue #2656):"]
    if orphans:
        lines.append(f"  {len(orphans)} orphan-queued run(s) (> {minutes:.0f} min, no open PR, head "
                     f"branch deleted):")
        for r in orphans:
            lines.append(f"    run {r['run']}  {r['workflow']}  branch={r['branch']}  head {r['head']}  "
                         f"created {r['created']}  ({r['minutes']:.1f} min)")
    if expired:
        lines.append(f"  {len(expired)} run(s) stuck `in_progress` whose job records have all "
                     f"concluded (job expiry, #1889):")
        for r in expired:
            lines.append(f"    run {r['run']}  {r['workflow']}  branch={r['branch']}  head {r['head']}  "
                         f"created {r['created']}  ({r['minutes']:.1f} min)")
    lines.append("")
    lines.append("Handling rule: an orphan-queued run is reported ONCE PER EPISODE, naming the run ids "
                 "and the orphan/live split above. It is NEVER cancelled by this alarm — the fleet "
                 "standing rule reserves cancellation for the owner's explicit word (docs/BOTS.md). "
                 "A permanently `in_progress` run whose jobs all concluded is job expiry (#1889): its "
                 "verdict is expired, not a live matrix, so it is not counted in the live queue.")
    return "\n".join(lines)


def run_marker(run_id: int) -> str:
    """The dedupe marker for one RUN: a newly stuck run is news, the same run is not."""
    return f"<!-- {MARKER}: run {run_id} -->"


def label_marker(label: str) -> str:
    """The dedupe marker for one runner LABEL (the fallback issue's marker)."""
    return f"<!-- {MARKER}: label {label} -->"


#: The run-level ghost-queue squat (issue #2656): orphan-queued runs (no open PR, head branch
#: deleted) and runs stuck `in_progress` whose job records have all concluded (job expiry, #1889).
SQUAT_MARKER = "queued-run-squat"


def episode_marker(run_ids: tuple[int, ...]) -> str:
    """The dedupe marker for ONE EPISODE: the same set of squatted run ids is one report, so the
    episode is keyed on the SORTED ids — adding a new squatted run makes the next report a fresh
    episode instead of silently being swallowed by the first one's marker."""
    return f"<!-- {MARKER}: {SQUAT_MARKER} episode {','.join(map(str, sorted(run_ids)))} -->"


def _run_list(repo: str, status: str, limit: int) -> list[dict]:
    """The repo's runs of one status with the fields the run-level classification needs."""
    return json.loads(_gh(["run", "list", "--repo", repo, "--status", status,
                           "--limit", str(limit),
                           "--json", "databaseId,workflowName,headBranch,headSha,createdAt,url,status"])
                      or "[]")

def open_prs_for_branch(repo: str, branch: str) -> list[int]:
    """The OPEN pull request numbers whose head is `branch` — empty when none (or no branch).

    The orphan classifier needs OPEN-only (unlike `run_prs` which falls back to a closed PR for
    delivery routing): a PR that merged leaving its branch deleted is exactly the just-finished
    work whose stale run is an orphan, not live work.
    """
    if not branch:
        return []
    prs = json.loads(_gh(["pr", "list", "--repo", repo, "--state", "all", "--head", branch,
                          "--json", "number,state"]) or "[]")
    return [p["number"] for p in prs if p.get("state") == "OPEN"]


def branch_resolved(repo: str, branch: str) -> bool:
    """Does the head branch still exist? Only a 404 (deleted) answers no.

    A transient read failure is treated as PRESENT, so a live run is never mis-called orphan on a
    network error: the 404 that the ghost-queue issue measures is an affirmative answer from GitHub
    that the ref is gone, and nothing else is that affirmative.
    """
    if not branch:
        return False
    try:
        _gh(["api", f"/repos/{repo}/git/ref/heads/{branch}"])
        return True
    except RuntimeError as err:
        return "404" not in str(err)


def squat_runs(repo: str, minutes: float = 30.0, limit: int = 30) -> tuple[list[dict], list[dict]]:
    """Classify the runs still non-terminal past `minutes` into (orphans, expired).

    ORPHAN: a run whose head branch has been deleted (404) and that no OPEN pull request tracks —
    the stale run of finished/past work squatting the queue (the 2026-11-11 ghost runs).

    EXPIRED: a run still `in_progress` whose job records have ALL concluded (every job has a
    conclusion; the ci-verdict self row is the residue). The run can never conclude on its own and
    must be read as JOB EXPIRY (#1889 wording), not as a live matrix — it does not count toward the
    live queued/in_progress supply.

    Neither is ever cancelled here: the fleet standing rule reserves cancellation for the owner's
    explicit word (see docs/BOTS.md).
    """
    now = dt.datetime.now(dt.timezone.utc)
    seen: set[int] = set()
    runs: list[dict] = []
    for status in ("queued", "in_progress"):
        for run in _run_list(repo, status, limit):
            rid = run.get("databaseId")
            if rid is None or rid in seen:
                continue
            seen.add(rid)
            runs.append(run)
    orphans: list[dict] = []
    expired: list[dict] = []
    for run in runs:
        rid = run.get("databaseId")
        age = _age_minutes(run.get("createdAt"), now)
        if age is None or age < minutes:
            continue
        branch = run.get("headBranch", "")
        jobs = json.loads(_gh(["run", "view", str(rid), "--repo", repo, "--json", "jobs"])
                          or "{}").get("jobs") or []
        row = {"run": rid,
               "workflow": run.get("workflowName", ""),
               "branch": branch,
               "head": (run.get("headSha") or "")[:12],
               "created": run.get("createdAt", ""),
               "url": run.get("url", ""),
               "minutes": age}
        if run.get("status") == "in_progress" and not any(
                (j.get("status") or "") in ("queued", "in_progress") for j in jobs):
            # Every job record concluded but the run stays in_progress: the job-expiry trap (#1889).
            expired.append(row)
            continue
        if open_prs_for_branch(repo, branch):
            continue
        if branch and not branch_resolved(repo, branch):
            # 404 on the head ref + no open PR: an orphan from finished work squatting queued.
            orphans.append(row)
    return (sorted(orphans, key=lambda r: -r["minutes"]) or [],
            sorted(expired, key=lambda r: -r["minutes"]) or [])

def run_prs(repo: str, run_id: int) -> list[int]:
    """The PR(s) this run reports on — empty when it is not a pull_request run.

    Resolved from the run's HEAD BRANCH, because neither shorter route works (both measured live
    against gh 2.102.0): `gh run view --json` rejects a `pullRequests` field outright ("Unknown
    JSON field"), and the REST run object's `pull_requests` array is EMPTY for a fork-PR run —
    which is exactly the shape this alarm sees (#277, #170). A read that fails raises, so `deliver`
    reports it instead of silently routing the report to the fallback issue.
    """
    data = json.loads(_gh(["api", f"/repos/{repo}/actions/runs/{run_id}"]) or "{}")
    if (data.get("event") or "") != "pull_request":
        return []
    branch = data.get("head_branch") or ""
    if not branch:
        return []
    prs = json.loads(_gh(["pr", "list", "--repo", repo, "--state", "all", "--head", branch,
                          "--json", "number,state"]) or "[]")
    open_prs = [p["number"] for p in prs if p.get("state") == "OPEN"]
    return open_prs or [p["number"] for p in prs][:1]


def _comments(repo: str, number: int) -> list[dict]:
    """Comments on a PR or an issue (the issues-comments endpoint serves both)."""
    try:
        return json.loads(_gh(["api", f"/repos/{repo}/issues/{number}/comments", "--paginate"])
                          or "[]")
    except (RuntimeError, ValueError):
        return []


def comment_run(repo: str, number: int, run_id: int, body: str, dry: bool = False) -> str:
    """Post ONE comment on `number` (a PR) about `run_id`; "" when posted or already there.

    Returns the failure reason otherwise, so the caller can be loud about a report that did not
    land. `number` must be a real PR/issue number — passing a run id here is the #294 bug.
    """
    if any(run_marker(run_id) in (c.get("body") or "") for c in _comments(repo, number)):
        return ""
    if dry:
        return ""
    r = subprocess.run(["gh", "api", "-X", "POST", f"/repos/{repo}/issues/{number}/comments",  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
                        "-f", f"body={body}\n\n_{run_marker(run_id)}_"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return (f"POST /repos/{repo}/issues/{number}/comments failed ({r.returncode}): "
                f"{r.stderr.strip()}")
    return ""


def file_label_issue(repo: str, label: str, body: str, dry: bool = False,
                     rows: list[dict] | None = None, minutes: float = 0.0) -> str:
    """ONE open issue per stuck runner LABEL, for the runs no PR tracks; "" when filed or open.

    A schedule or `push` run has no PR to comment on, and a missing runner is a property of the
    LABEL, not of one run — so the fallback is one deduped issue per label, never one per run. The
    body is the shape every issue in this repository carries (issue #745); the raw report is its
    `## Technical` detail.
    """
    try:
        found = json.loads(_gh(["issue", "list", "--repo", repo, "--state", "open",
                                "--search", f"{label} in:body",
                                "--json", "number,body"]) or "[]")
    except (RuntimeError, ValueError):
        found = []
    if any(label_marker(label) in (i.get("body") or "") for i in found):
        return ""
    if dry:
        return ""
    count = len(rows) if rows else 0
    text = issue_body.render(
        problem=(
            f"No runner matches the label `{label}`: "
            f"{f'{count} job(s) have' if count else 'jobs have'} been queued longer than "
            f"{minutes:.0f} minutes with no machine to pick them up, in run(s) no pull request "
            "tracks."
        ),
        why=(
            "GitHub does not fail a job whose runner never arrives — it stays `queued` and the run "
            "never concludes, so every pull request's checks stay pending and the work looks slow "
            "instead of stuck (issue #254)."
        ),
        how=[
            "Bring a runner back for that label: a self-hosted runner is offline or unregistered, "
            "or the account's hosted-runner minutes/spending limit for that OS is exhausted.",
            "Re-dispatch the affected run once a runner exists: a queued job does not start by "
            "itself.",
            "If the label is retired, remove it from the workflow that asks for it.",
        ],
        benefit=(
            "A missing runner becomes one filed work item naming the label that is missing, instead "
            "of a silent pile of pending checks that nobody can distinguish from a slow queue."
        ),
        acceptance=[
            f"a runner matching `{label}` picks up new runs again",
            "the runs named in the report below conclude instead of staying queued",
        ],
        technical=[
            f"label: `{label}`",
            f"threshold: queued longer than {minutes:.0f} minutes",
            body,  # already a fenced report: pasted as a block, not as a bullet
        ],
    )
    title = f"ci: no runner matches `{label}` — jobs are queued with no machine to run them"
    r = subprocess.run(["gh", "issue", "create", "--repo", repo, "--title", title,  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
                        "--body", f"{text}\n\n_{label_marker(label)}_"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return f"issue create for `{label}` failed ({r.returncode}): {r.stderr.strip()}"
    return ""


def file_squat_issue(repo: str, orphans: list[dict], expired: list[dict], minutes: float,
                     dry: bool = False) -> str:
    """File ONE deduped issue per EPISODE of ghost-queue squat; \"\" when already on file.

    The episode is keyed on the sorted run-id set, so the alarm reports the same squat once; a NEW
    squatted run joins the ring and the next report is a fresh episode (never swallowed by an old
    marker). The dedupe reads issues open OR closed — a squat that persists after an issue closes is
    not re-spammed daily (the #2584 phantom-spam pattern); a changed run set is a fresh episode.
    Rendered through the one issue-body renderer. Never cancels any run.
    """
    ids = sorted({r["run"] for r in orphans} | {r["run"] for r in expired})
    if not ids:
        return ""
    marker = episode_marker(tuple(ids))
    try:
        found = json.loads(_gh(["issue", "list", "--repo", repo, "--state", "all", "--limit", "300",
                                "--search", f'"{marker}" in:body', "--json", "body"]) or "[]")
    except (RuntimeError, ValueError):
        found = []
    if any(marker in (i.get("body") or "") for i in found):
        return ""
    if dry:
        return ""
    rows = orphans + expired
    text = issue_body.render(
        problem=(
            f"{len(rows)} CI run(s) have squatted in non-terminal states past "
            f"{minutes:.0f} minutes while this alarm fires: "
            f"{len(orphans)} orphan-queued run(s) (no open PR, head branch deleted: "
            + ", ".join(f"`{r['run']}`" for r in orphans) + ")"
            + (f" and {len(expired)} run(s) stuck `in_progress` whose jobs have all concluded "
               f"(job expiry): " + ", ".join(f"`{r['run']}`" for r in expired) if expired else "")
            + "."
        ),
        why=(
            "Squatted runs poison queue telemetry: an eternal `in_progress` run misreads as a live "
            "matrix and days-old orphan-queued rows make the queued count untrustworthy "
            "(issue #2656)."
        ),
        how=[
            "Name the runs below and classify each as orphan queued (no open PR, head "
            "branch deleted) or expired in_progress (job records all concluded, #1889).",
            "The alarm NEVER cancels any run it names: the fleet standing rule reserves "
            "cancellation for the owner's explicit word — a manual `gh run cancel <id>` is the "
            "only path.",
            "A permanently `in_progress` run whose job records have concluded is job expiry "
            "(#1889): its verdict is expired, not gate damage, and it no longer counts toward the "
            "live queue.",
            "Re-dispatch or clean up the runs only with the owner's decision; deleting a phantom "
            "row is admin-only (see the zero-job zombie retirement, issue #2600).",
        ],
        benefit=(
            "Queue telemetry becomes trustworthy: `queued`/`in_progress` counts reflect work that "
            "can actually start, and a ghost-run squat is reported once per episode instead of "
            "being indistinguishable from a live queue."
        ),
        acceptance=[
            "the run ids below are reported once per episode with the orphan/expired split",
            "the runs are never cancelled by this alarm",
            "an expired in_progress run is not counted as a live matrix",
        ],
        technical=[
            "producer: scripts/queued_run_alarm.py (file_squat_issue; episode marker `queued-run-squat`; "
            "spec openspec/changes/ci-queued-squat-classify/)",
            "episode marker: " + marker,
            "threshold: non-terminal past {:.0f} minutes".format(minutes),
            render_squat(orphans, expired, minutes),
        ],
    )
    title = (f"ci: {len(rows)} ghost run(s) squat queued/in_progress — "
             f"{len(orphans)} orphan queued, {len(expired)} expired in_progress (job expiry)")
    r = subprocess.run(["gh", "issue", "create", "--repo", repo, "--title", title,  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
                        "--body", f"{text}\n\n_{marker}_"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return f"issue create for squat episode failed ({r.returncode}): {r.stderr.strip()}"
    return ""


def deliver(repo: str, rows: list[dict], minutes: float, dry: bool = False) -> list[str]:
    """Send the report where a human will read it; return the deliveries that FAILED.

    A run that reports on a PR is commented on that PR (one comment per run); a run no PR tracks
    contributes its label to the per-label fallback issue.
    """
    by_run: dict[int, list[dict]] = {}
    for r in rows:
        by_run.setdefault(r["run"], []).append(r)

    failures: list[str] = []
    orphan: dict[str, list[dict]] = {}
    for run_id, run_rows in sorted(by_run.items()):
        try:
            prs = run_prs(repo, run_id)
        except RuntimeError as err:
            # Loud, AND the report still lands somewhere a human reads (the per-label fallback).
            failures.append(f"could not read the pull requests of run {run_id}: {err}")
            prs = []
        if not prs:
            for r in run_rows:
                orphan.setdefault(r["labels"] or "(no label)", []).append(r)
            continue
        body = (f"The queued-run alarm found jobs stuck in this run "
                f"({run_rows[0]['workflow']} on `{run_rows[0]['branch']}`):\n\n"
                f"```\n{render(run_rows, minutes)}\n```")
        for pr in prs:
            why = comment_run(repo, pr, run_id, body, dry=dry)
            if why:
                failures.append(why)

    for label, label_rows in sorted(orphan.items()):
        body = (f"{len(label_rows)} job(s) have been queued on `{label}` for longer than "
                f"{minutes:.0f} minutes, in run(s) no pull request tracks:\n\n"
                f"```\n{render(label_rows, minutes)}\n```")
        why = file_label_issue(repo, label, body, dry=dry, rows=label_rows, minutes=minutes)
        if why:
            failures.append(why)
    return failures


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True, help="owner/name")
    ap.add_argument("--minutes", type=float, default=30.0,
                    help="how long a job may stay queued before it is reported")
    ap.add_argument("--comment", action="store_true",
                    help="deliver the report (the run's PR, else one issue per stuck label), "
                         "deduplicated")
    ap.add_argument("--dry", action="store_true",
                    help="print what --comment would post, and post nothing")
    ap.add_argument("--limit", type=int, default=30, help="how many in-progress runs to inspect")
    a = ap.parse_args(argv)

    try:
        rows = stuck_jobs(a.repo, a.minutes, limit=a.limit)
    except RuntimeError as err:
        print(f"[queued-alarm] {err}", file=sys.stderr, flush=True)
        return 2
    print(f"[queued-alarm] {render(rows, a.minutes)}", flush=True)

    try:
        orphans, expired = squat_runs(a.repo, a.minutes, limit=a.limit)
    except RuntimeError as err:
        print(f"[queued-alarm] squat read failed: {err}", file=sys.stderr, flush=True)
        return 2
    print(render_squat(orphans, expired, a.minutes), flush=True)

    has_squat = bool(orphans or expired)
    if not rows and not has_squat:
        return 0

    if a.comment or a.dry:
        failures = deliver(a.repo, rows, a.minutes, dry=a.dry)
        why_squat = file_squat_issue(a.repo, orphans, expired, a.minutes, dry=a.dry)
        if why_squat:
            failures.append(why_squat)
        if failures:
            # The alarm whose report goes nowhere was #294: a delivery failure is never silent.
            for why in failures:
                print(f"[queued-alarm] DELIVERY FAILED: {why}", file=sys.stderr, flush=True)
            return 3
        squat_note = (f", squat episode {len(orphans) + len(expired)} run(s)" if has_squat else "")
        print(f"[queued-alarm] report {'would be ' if a.dry else ''}delivered "
              f"({len(rows)} stuck job(s), {len({r['run'] for r in rows})} run(s)"
              f"{squat_note})", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
