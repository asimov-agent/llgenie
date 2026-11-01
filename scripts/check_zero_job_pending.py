"""Flag a dispatched run that instantiates ZERO jobs and sits `pending` far too long (issue #1410).

`queued_run_alarm` (issue #254) scans a run's JOB ROWS for stuck `queued` jobs. A run whose
workflow instantiates no jobs at all — a runner-starvated dispatch, e.g. `engine-build` vllm-cuda
with no large/self-hosted runner — has `jobs.total_count == 0`, so the alarm's job-row scan sees
nothing and reports "no job has been queued longer than 30 minutes" while the run stays `pending`
forever. This is the RUN-LEVEL complement: it lists the repo's queued/in-progress runs and flags
the ones that have been `pending`/`queued` for longer than `--minutes` with **zero** jobs
instantiated, naming the run id, head sha, created time and the workflow. `ci_verdict` (line ~100)
only pagination-warns when `total_count > len(jobs)`; `check_workflows` only catches a
`completed/failure` zero-job run (a workflow rejected at LOAD); neither sees a zero-job run still
`pending`.

Measurement (2026-11-01, #1410): run 41321206783 (event workflow_dispatch, head f41685f3,
engine-build.yml) was `pending`/`queued` with `jobs.total_count == 0` from 15:26:09Z until it was
cancelled at 15:47:45Z; the `engine-build-push` concurrency group was empty (no other run held it)
and the runner pool read returned 403 (no runner matched `vllm-cuda`). Nothing named this run.

Exit codes: 0 = no zero-job run stuck, 1 = at least one, 2 = the GitHub read failed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import issue_body  # noqa: E402  (the one issue shape, #745)
from proc import run_ok  # noqa: E402  the subprocess policy seam (issue #797)

MARKER = "zero-job-pending"


def _run_marker(run_id: int) -> str:
    """The dedupe marker for one RUN: a newly stuck run is news, the same run is not."""
    return f"<!-- {MARKER}: run {run_id} -->"


def _gh(args: list[str]) -> str:
    r = run_ok(["gh", *args])
    if r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout


def _age_minutes(created: str | None, now: dt.datetime) -> float | None:
    """Minutes since a run's creation. GitHub sets created_at when the dispatch is accepted."""
    if not created:
        return None
    try:
        t = dt.datetime.strptime(created, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except ValueError:
        try:
            t = dt.datetime.fromisoformat(created.replace("Z", "+00:00"))
        except ValueError:
            return None
    return round((now - t).total_seconds() / 60.0, 1)


def zero_job_pending_runs(repo: str, minutes: float = 30.0, now: dt.datetime | None = None,
                          limit: int = 100) -> list[dict]:
    """Runs in this repo still `queued`/`in_progress` with zero jobs, past `minutes`."""
    now = now or dt.datetime.now(dt.timezone.utc)
    seen: set[int] = set()
    candidates: list[dict] = []
    for status in ("queued", "in_progress"):
        runs = json.loads(_gh(["run", "list", "--repo", repo, "--status", status,
                               "--limit", str(limit),
                               "--json", "databaseId,workflowName,headBranch,headSha,createdAt,url"])
                          or "[]")
        for run in runs:
            rid = run.get("databaseId")
            if rid is None or rid in seen:
                continue
            seen.add(rid)
            candidates.append(run)
    out: list[dict] = []
    for run in candidates:
        rid = run.get("databaseId")
        jobs = json.loads(_gh(["run", "view", str(rid), "--repo", repo, "--json", "jobs"]) or "{}")
        total = int((jobs.get("total_count") if isinstance(jobs, dict) else None) or 0)
        if total != 0:
            continue
        age = _age_minutes(run.get("createdAt"), now)
        if age is None or age < minutes:
            continue
        out.append({"run": rid,
                    "workflow": run.get("workflowName", ""),
                    "branch": run.get("headBranch", ""),
                    "head": (run.get("headSha") or "")[:12],
                    "created": run.get("createdAt", ""),
                    "url": run.get("url", ""),
                    "minutes": age})
    return sorted(out, key=lambda r: -r["minutes"])


def render(rows: list[dict], minutes: float) -> str:
    """The report a human reads: which dispatched runs never got a single job."""
    if not rows:
        return f"no run has been pending/queued longer than {minutes:.0f} minutes with zero jobs"
    lines = [f"{len(rows)} run(s) pending/queued longer than {minutes:.0f} minutes with ZERO jobs:", ""]
    for r in rows:
        lines.append(f"  {r['minutes']:7.1f} min  run {r['run']}  {r['workflow']}  "
                     f"branch={r['branch']}  head {r['head']}  created {r['created']}")
    lines += ["",
              "A dispatched run that instantiates NO jobs stays `pending` with no alarm: "
              "`queued_run_alarm` scans job rows (there are none) and `run-failure-reactor` needs a "
              "failure/cancelled/timed_out conclusion (a pending run has none). A runner that never "
              "arrives for the requested labels, or a missing/offline self-hosted runner, is the usual "
              "cause — see issue #1410."]
    return "\n".join(lines)


def file_one_issue(repo: str, r: dict, body: str, dry: bool = False) -> str:
    """File ONE deduped issue for a stuck run; "" when filed or already open.

    Files once per run (marker in the body), idempotent: a run already reported is not reported
    again. Returns the failure reason otherwise, so the monitor can be loud about a report that
    did not land (a delivery that fails is worse than no alarm, #294)."""
    rid = r["run"]
    try:
        found = json.loads(_gh(["issue", "list", "--repo", repo, "--state", "open",
                                "--search", f"{rid} in:body", "--json", "body"]) or "[]")
    except (RuntimeError, ValueError):
        found = []
    if any(_run_marker(rid) in (i.get("body") or "") for i in found):
        return ""
    if dry:
        return ""
    text = issue_body.render(
        problem=(
            f"A dispatched run instantiates **zero jobs** and stays `pending`/`queued` past the "
            f"freshness threshold: `{r['workflow']}` on `{r['branch']}` (head {r['head']}, "
            f"created {r['created']}). No runner matched the requested labels and nothing named "
            f"the run."
        ),
        why=(
            "GitHub does not fail a run whose workflow instantiates no jobs — it stays `pending` "
            "indefinitely, `queued_run_alarm` scans job rows (there are none) and reads clean, and "
            "`run-failure-reactor` needs a failure/cancelled/timed_out conclusion a pending run "
            "does not have. A stuck dispatch becomes an eternal 'pending' that looks like work in "
            "progress (issue #1410)."
        ),
        how=[
            "Match a runner to the requested labels (a self-hosted runner is offline/unregistered, "
            "or the account's hosted-runner capacity for that OS is exhausted).",
            "Re-dispatch the run once a runner exists — a zero-job run does not start by itself.",
        ],
        benefit=(
            "A runner-starved dispatch becomes ONE filed work item naming the run, instead of a "
            "silent pending placeholder nobody can distinguish from a working matrix."
        ),
        acceptance=[
            "the run named below instantiates its jobs and concludes",
            "a zero-job `pending` run is never reported a second time",
        ],
        technical=[f"run: `{rid}`", f"threshold: pending/queued longer than past the --minutes threshold", body],
    )
    title = f"ci: run {rid} instantiates zero jobs and stays pending — no runner matched the labels"
    rq = run_ok(["gh", "issue", "create", "--repo", repo, "--title", title,
                 "--body", f"{text}\n\n_{_run_marker(rid)}_"])
    if rq.returncode != 0:
        return f"issue create for run {rid} failed ({rq.returncode}): {rq.stderr.strip()}"
    return ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Flag dispatched runs pending/queued too long with zero jobs")
    ap.add_argument("--repo", required=True, help="owner/repo")
    ap.add_argument("--minutes", type=float, default=30.0, help="threshold minutes (default 30)")
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--file", action="store_true",
                    help="file ONE deduped issue per stuck run (idempotent by run-id marker)")
    args = ap.parse_args(argv)
    try:
        rows = zero_job_pending_runs(args.repo, minutes=args.minutes, limit=args.limit)
    except RuntimeError as e:
        print(f"[{MARKER}] github read failed: {e}", file=sys.stderr)
        return 2
    print(render(rows, args.minutes))
    if not rows:
        return 0
    if args.file:
        failures = []
        for r in rows:
            why = file_one_issue(args.repo, r, render([r], args.minutes))
            if why:
                failures.append(why)
        if failures:
            for why in failures:
                print(f"[{MARKER}] DELIVERY FAILED: {why}", file=sys.stderr)
            return 3
        print(f"[{MARKER}] filed {len(rows)} deduped issue(s) naming the stuck run(s)", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
