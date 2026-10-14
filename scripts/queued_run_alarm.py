"""Report jobs that have been queued far too long, so a stuck runner is loud (issue #254).

When a runner label matches nothing (an offline self-hosted runner, or hosted macOS minutes
exhausted), GitHub does not fail the job — it leaves it `queued` forever. The run never
concludes, `mergeStateStatus` stays BLOCKED, and every PR's checks sit at "pending" with no
signal anywhere that anything is wrong. This makes that state loud:

  * list the in-progress runs of a repo, then the jobs still `queued`,
  * flag the ones queued longer than `--minutes` (default 30),
  * print a table that names the runner label and the age, and
  * `--comment` posts ONE comment on each affected run, deduplicated against its own previous
    comments, so a repeated sweep does not spam.

Exit codes: 0 = nothing stuck, 1 = at least one job is stuck (so a scheduled job goes red), 2 =
the GitHub call failed. Read-only apart from the optional comment.
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


def comment_run(repo: str, run_id: int, body: str) -> None:
    """One comment per run, deduplicated against this tool's own previous comments."""
    try:
        existing = json.loads(_gh(["api", f"/repos/{repo}/issues/{run_id}/comments", "--paginate"])
                              or "[]")
    except RuntimeError:
        existing = []
    if any(MARKER in (c.get("body") or "") for c in existing):
        return
    subprocess.run(["gh", "api", "-X", "POST", f"/repos/{repo}/issues/{run_id}/comments",
                    "-f", f"body={body}\n\n_<!-- {MARKER} -->_"],
                   capture_output=True, text=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True, help="owner/name")
    ap.add_argument("--minutes", type=float, default=30.0,
                    help="how long a job may stay queued before it is reported")
    ap.add_argument("--comment", action="store_true",
                    help="comment once on each affected run (deduplicated)")
    ap.add_argument("--limit", type=int, default=30, help="how many in-progress runs to inspect")
    a = ap.parse_args(argv)

    try:
        rows = stuck_jobs(a.repo, a.minutes, limit=a.limit)
    except RuntimeError as err:
        print(f"[queued-alarm] {err}", file=sys.stderr, flush=True)
        return 2
    print(f"[queued-alarm] {render(rows, a.minutes)}", flush=True)
    if rows and a.comment:
        for run_id in sorted({r["run"] for r in rows}):
            body = render([r for r in rows if r["run"] == run_id], a.minutes)
            comment_run(a.repo, run_id, f"The queued-run alarm found jobs stuck in this run:\n\n```\n{body}\n```")
    return 1 if rows else 0


if __name__ == "__main__":
    raise SystemExit(main())
