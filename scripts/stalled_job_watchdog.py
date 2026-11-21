#!/usr/bin/env python3
"""The stalled-job watchdog: an in_progress job past its budget is named while the run is live (issue #2992).

Every existing monitor watches whole RUNS. A run that is NOT job-less (#1410), NOT queue-starved
(#917) and NOT frozen (#923, 90-min `updated_at` threshold) is invisible to all of them while it sits
on a hung job. Measured 2026-11-21T04:23Z: run `44863652918` (auto-merge's trigger CI for PR #2990
head `8d4892e6797238fae9300fdedf26e138734d575b`) had every job conclude within ~1 min except
`linux/unit` (job `136722618230`), `in_progress` since 03:57:56Z with `updated_at` frozen at
03:57:57Z. The run stayed `in_progress` until 04:23:54Z, so `ci-verdict` (a `workflow_run` on
completion) never judged that head and `auto-merge.yml` (triggered by the verdict) never armed the
merge — the 26-minute idle SILENCED the merge chain for the whole wedge window.

The watchdog flags the class the moment it crosses a job-specific budget: a run with at least one
already-CONCLUDED job (so the run demonstrably got runners) plus an `in_progress` job older than

    max(STALL_FLOOR, STALL_FACTOR x median wall time of that job's NAME in the workflow's recent completed runs)

with a named fallback budget when the job name has no history. `--file` posts ONE deduped comment on
the run head's PR (marker `<!-- stalled-job-watchdog: run <id> job <job-id> -->`); a run with no PR is
named in the report only. It never cancels and never re-runs: cancel policy stays with the zero-job
(#1410) and frozen-reaper lanes. Exit: 0 nothing new / 1 findings without --file / 2 read failure /
3 delivery failure.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPO = "asimov-agent/llgenie"

# The budget constants are the spec's (openspec stalled-job-watchdog): floor 15 min, factor 1.25,
# 60-min fallback when the job name has no completed history, 8 recent runs sampled per workflow.
STALL_FLOOR_MINUTES = 15.0
STALL_FACTOR = 1.25
FALLBACK_MINUTES = 60.0
HISTORY_RUNS = 8
MARKER = "stalled-job-watchdog"
RUN_JSON = "databaseId,workflowName,headBranch,headSha,createdAt,updatedAt,url"
CONCLUDED = ("success", "failure")


def _iso_utc(ts: "str | None") -> datetime | None:
    try:
        return datetime.fromisoformat(str(ts).strip().replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _minutes(a: datetime, b: datetime) -> float:
    return (b - a).total_seconds() / 60.0


def _gh(args: list[str], timeout: int = 90) -> subprocess.CompletedProcess:
    return subprocess.run(["gh"] + args, capture_output=True, text=True, timeout=timeout)


def run_ok(args: list[str], repo: str, now: datetime, what: str, errors: list[str],
           timeout: int = 90) -> dict | list | None:
    p = _gh(args, timeout=timeout)
    if p.returncode != 0:
        errors.append(f"{what} ({p.returncode}): {(p.stderr or p.stdout).strip()[:240]}")
        return None
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        errors.append(f"{what}: unparseable answer: {p.stdout[:240]}")
        return None


def _job_walls(jobs: list[dict]) -> dict[str, list[float]]:
    """Wall minutes per CONCLUDED job name from one run's job rows."""
    walls: dict[str, list[float]] = {}
    for j in jobs:
        if j.get("status") != "completed" or j.get("conclusion") not in CONCLUDED:
            continue
        start, end = _iso_utc(j.get("startedAt")), _iso_utc(j.get("completedAt"))
        if start is None or end is None or end < start:
            continue
        walls.setdefault(j.get("name") or "?", []).append(_minutes(start, end))
    return walls


def _median_walls(repo: str, workflow: str, now: datetime, errors: list[str],
                  history: int, cache: dict) -> dict[str, float]:
    """Median wall minutes per job name across the workflow's recent completed runs."""
    if workflow in cache:
        return cache[workflow]
    medians: dict[str, list[float]] = {}
    runs = run_ok(["run", "list", "--repo", repo, "--workflow", workflow,
                   "--limit", str(max(history, 1)), "--json", "databaseId,conclusion"],
                  repo, now, f"run-list history for {workflow!r}", errors) or []
    for r in runs:
        if r.get("conclusion") not in CONCLUDED:
            continue
        jobs = run_ok(["run", "view", str(r.get("databaseId")), "--repo", repo, "--json", "jobs"],
                      repo, now, f"run-view {r.get('databaseId')}", errors)
        if not isinstance(jobs, dict):
            continue
        for name, walls in _job_walls(jobs.get("jobs") or []).items():
            medians.setdefault(name, []).extend(walls)
    cache[workflow] = {name: median(walls) for name, walls in medians.items() if walls}
    return cache[workflow]


def stalled_runs(repo: str, now: datetime, floor: float = STALL_FLOOR_MINUTES,
                 factor: float = STALL_FACTOR, fallback: float = FALLBACK_MINUTES,
                 history: int = HISTORY_RUNS, limit: int = 25) -> tuple[list[dict], list[str]]:
    """Findings: runs with a concluded sibling job + an in_progress job past its named budget."""
    errors: list[str] = []
    listed = run_ok(["run", "list", "--repo", repo, "--status", "in_progress",
                     "--limit", str(limit), "--json", RUN_JSON],
                    repo, now, "run-list in_progress", errors, timeout=120)
    runs = listed if isinstance(listed, list) else []
    findings: list[dict] = []
    med_cache: dict[str, dict[str, float]] = {}
    for r in runs:
        rid = r.get("databaseId")
        jobs = run_ok(["run", "view", str(rid), "--repo", repo, "--json", "jobs"],
                      repo, now, f"run-view {rid}", errors)
        if not isinstance(jobs, dict):
            continue
        rows = jobs.get("jobs") or []
        # The run must show progress: at least one concluded job, or it is the queued/frozen lanes' domain.
        if not any(j.get("status") == "completed" for j in rows):
            continue
        medians = _median_walls(repo, r.get("workflowName") or "", now, errors, history, med_cache)
        for j in rows:
            if j.get("status") != "in_progress":
                continue
            started = _iso_utc(j.get("startedAt")) or _iso_utc(r.get("createdAt"))
            if started is None:
                continue
            elapsed = _minutes(started, now)
            if elapsed < floor:
                continue
            name = j.get("name") or "?"
            if name in medians:
                budget = max(floor, factor * medians[name])
                deriv = (f"{factor} x median job wall {medians[name]:.1f} min "
                         f"(floor {floor:.0f} min)")
            else:
                budget = max(floor, fallback)
                deriv = f"fallback {fallback:.0f} min (no completed history for job {name!r})"
            if elapsed <= budget:
                continue
            findings.append({
                "run_id": rid, "workflow": r.get("workflowName") or "?",
                "branch": r.get("headBranch") or "?", "head_sha": r.get("headSha") or "",
                "url": r.get("url") or f"https://github.com/{repo}/actions/runs/{rid}",
                "job_id": j.get("id") or j.get("databaseId") or name, "job": name,
                "started": (j.get("startedAt") or r.get("createdAt") or "?"),
                "elapsed": elapsed, "budget": budget, "derivation": deriv,
            })
    return findings, errors


def _pr_for_run(repo: str, sha: str, now: datetime, errors: list[str]) -> int | None:
    pulls = run_ok(["api", f"repos/{repo}/commits/{sha}/pulls"], repo, now,
                   f"pulls-for-head {sha[:7]}", errors) or []
    if not isinstance(pulls, list):
        return None
    for pr in pulls:
        if pr.get("state") == "open":
            return pr.get("number")
    return pulls[0].get("number") if pulls else None


def _already_commented(repo: str, pr: int, marker_text: str, now: datetime,
                       errors: list[str]) -> bool:
    comments = run_ok(["api", f"repos/{repo}/issues/{pr}/comments", "--paginate"],
                      repo, now, f"comments-of-pr #{pr}", errors) or []
    if not isinstance(comments, list):
        return False
    return any(marker_text in (c.get("body") or "") for c in comments)


def _comment_body(f: dict) -> str:
    return (
        "stalled-job-watchdog: this run has a stalled `in_progress` job while its sibling jobs "
        f"already concluded (issue #2992 — the class that silenced the verdict and merge sweep for "
        f"26 minutes on run `44863652918`).\n\n"
        f"- job: **{f['job']}** (id `{f['job_id']}`) running **{f['elapsed']:.0f} min**, "
        f"budget **{f['budget']:.0f} min** = {f['derivation']}\n"
        f"- started: `{f['started']}` · run: {f['url']} "
        f"(branch `{f['branch']}` @ `{str(f['head_sha'])[:10]}`)\n\n"
        "Named, not cancelled: cancelling or capping stalled runs is out of scope for issue #2992 — "
        "the zero-job (#1410) and frozen-reaper lanes keep the cancel policy.\n"
        f"<!-- {MARKER}: run {f['run_id']} job {f['job_id']} -->"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="name stalled in_progress jobs (issue #2992)")
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument("--floor", type=float, default=STALL_FLOOR_MINUTES,
                    help="minimum elapsed minutes before a job can be named")
    ap.add_argument("--factor", type=float, default=STALL_FACTOR,
                    help="budget = factor x median wall time of the job name")
    ap.add_argument("--fallback-minutes", type=float, default=FALLBACK_MINUTES,
                    help="budget when the job name has no completed history")
    ap.add_argument("--history", type=int, default=HISTORY_RUNS,
                    help="recent completed runs sampled per workflow")
    ap.add_argument("--limit", type=int, default=25, help="in_progress runs scanned")
    ap.add_argument("--file", action="store_true",
                    help="post the deduped comment on the run head's PR (the lane default)")
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args(argv)

    now = datetime.now(timezone.utc)
    findings, errors = stalled_runs(args.repo, now, floor=args.floor, factor=args.factor,
                                    fallback=args.fallback_minutes, history=args.history,
                                    limit=args.limit)
    if args.as_json:
        print(json.dumps({"findings": findings, "errors": errors}, indent=2))
    else:
        for f in findings:
            print(f"  STALL  run {f['run_id']} ({f['workflow'][:50]}) branch {f['branch']}: "
                  f"job {f['job']!r} in_progress {f['elapsed']:.0f} min past budget "
                  f"{f['budget']:.0f} min = {f['derivation']}")
        if findings:
            print(f"STALLED-JOB WATCHDOG: {len(findings)} stalled job(s) named above "
                  "(the run is left running; cancel policy stays with the zero-job/frozen lanes).")
        else:
            print("STALLED-JOB WATCHDOG: no run has an in_progress job past its budget.")

    if errors:
        print(f"READ FAILURE ({len(errors)} gh read(s) failed):", file=sys.stderr)
        for e in errors[:10]:
            print(f"  {e}", file=sys.stderr)
        return 2

    if not findings:
        return 0

    if not args.file:
        return 1

    delivered = already_named = failed = 0
    for f in findings:
        pr = _pr_for_run(args.repo, f["head_sha"], now, errors) if f["head_sha"] else None
        if pr is None:
            print(f"  run {f['run_id']} belongs to no PR — named in this report only (no filing).")
            already_named += 1
            continue
        marker_text = f"{MARKER}: run {f['run_id']} job {f['job_id']}"
        if _already_commented(args.repo, pr, marker_text, now, errors):
            print(f"  run {f['run_id']} job {f['job']!r} already named on PR #{pr} — no second comment.")
            already_named += 1
            continue
        p = _gh(["issue", "comment", str(pr), "--repo", args.repo, "--body", _comment_body(f)])
        if p.returncode == 0:
            print(f"  filed stalled-job comment on PR #{pr} (run {f['run_id']} job {f['job']!r}).")
            delivered += 1
        else:
            failed += 1
            print(f"  FAILED to comment on PR #{pr}: {(p.stderr or p.stdout).strip()[:200]}",
                  file=sys.stderr)
    if errors:  # a read failed during the present phase
        print("READ FAILURE during delivery:", file=sys.stderr)
        for e in errors[:10]:
            print(f"  {e}", file=sys.stderr)
        return 2
    print(f"STALLED-JOB DELIVERY: {delivered} new comment(s), {already_named} already named, "
          f"{failed} failed.")
    return 3 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
