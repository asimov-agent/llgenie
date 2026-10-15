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

Exit codes: 0 = nothing stuck, 1 = at least one job is stuck (so a scheduled job goes red), 2 = the
GitHub read failed, 3 = jobs are stuck AND the report could not be delivered.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys

MARKER = "queued-run-alarm"


def _gh(args: list[str]) -> str:
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
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


def run_marker(run_id: int) -> str:
    """The dedupe marker for one RUN: a newly stuck run is news, the same run is not."""
    return f"<!-- {MARKER}: run {run_id} -->"


def label_marker(label: str) -> str:
    """The dedupe marker for one runner LABEL (the fallback issue's marker)."""
    return f"<!-- {MARKER}: label {label} -->"


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
    r = subprocess.run(["gh", "api", "-X", "POST", f"/repos/{repo}/issues/{number}/comments",
                        "-f", f"body={body}\n\n_{run_marker(run_id)}_"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return (f"POST /repos/{repo}/issues/{number}/comments failed ({r.returncode}): "
                f"{r.stderr.strip()}")
    return ""


def file_label_issue(repo: str, label: str, body: str, dry: bool = False) -> str:
    """ONE open issue per stuck runner LABEL, for the runs no PR tracks; "" when filed or open.

    A schedule or `push` run has no PR to comment on, and a missing runner is a property of the
    LABEL, not of one run — so the fallback is one deduped issue per label, never one per run.
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
    title = f"ci: no runner matches `{label}` — jobs are queued with no machine to run them"
    r = subprocess.run(["gh", "issue", "create", "--repo", repo, "--title", title,
                        "--body", f"{body}\n\n_{label_marker(label)}_"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return f"issue create for `{label}` failed ({r.returncode}): {r.stderr.strip()}"
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
        why = file_label_issue(repo, label, body, dry=dry)
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
    if not rows:
        return 0

    if a.comment or a.dry:
        failures = deliver(a.repo, rows, a.minutes, dry=a.dry)
        if failures:
            # The alarm whose report goes nowhere was #294: a delivery failure is never silent.
            for why in failures:
                print(f"[queued-alarm] DELIVERY FAILED: {why}", file=sys.stderr, flush=True)
            return 3
        print(f"[queued-alarm] report {'would be ' if a.dry else ''}delivered "
              f"({len(rows)} stuck job(s), {len({r['run'] for r in rows})} run(s))", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
