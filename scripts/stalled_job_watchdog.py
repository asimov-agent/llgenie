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
named in the report only. `--cancel-stalled` (issue #2997, the policy #2992 deferred) ENDS a
classified run via `gh run cancel`, gated by four proofs evaluated at cancel time: (1) the run still
matches this watchdog's own stalled classification — no new threshold, no new class; (2) a LIVE
re-read immediately before the cancel — a stalled job that concluded since classification SKIPS the
cancel (the #1822/#1823 rule: a live job is never touched); (3) only a head carrying an OPEN,
NON-DRAFT pull request is cancellable — no-PR (push/schedule/main) runs stay named only, the
zero-job (#1410) and frozen-reaper lanes' domain; (4) a cancel racing a conclusion ("...is
completed") is a benign race, not a delivery failure (the #1410 `--cancel-stranded` precedent).
A cancel ENDS a run and never starts one: the watchdog never dispatches, reruns, or re-triggers;
recovery after a cancel arrives only through GitHub events (push, PR synchronize, label) or a human.
Cancel BEFORE filing so the comment states the real outcome (`cancelled` / `skipped: <why>` /
benign race); without `--cancel-stalled` the watchdog names only, exactly as in #2992.
Exit: 0 nothing new / 1 findings without --file / 2 read failure / 3 delivery failure.
"""
from __future__ import annotations

import argparse
import json
import proc
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


def _gh(args: list[str], timeout: int = 90) -> subprocess.CompletedProcess[str]:
    # scripts/proc.py is the ONE subprocess policy seam (issue #797); the gh reads
    # go through proc.run_ok because a failed gh call is a branch this monitor
    # handles (it reports the read failure and exits 2), not a raise.
    return proc.run_ok(["gh"] + args, timeout=timeout)


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


def _pr_for_run(repo: str, sha: str, now: datetime, errors: list[str]) -> tuple[int | None, bool, bool]:
    """(PR number, is_draft, is_open) for the run head; (None, False, False) when the head carries no PR."""
    pulls = run_ok(["api", f"repos/{repo}/commits/{sha}/pulls"], repo, now,
                   f"pulls-for-head {sha[:7]}", errors) or []
    if not isinstance(pulls, list):
        return None, False, False
    for pr in pulls:
        if pr.get("state") == "open":
            return pr.get("number"), bool(pr.get("draft")), True
    return (pulls[0].get("number"), bool(pulls[0].get("draft")), False) if pulls else (None, False, False)


def _already_commented(repo: str, pr: int, marker_text: str, now: datetime,
                       errors: list[str]) -> bool:
    comments = run_ok(["api", f"repos/{repo}/issues/{pr}/comments", "--paginate"],
                      repo, now, f"comments-of-pr #{pr}", errors) or []
    if not isinstance(comments, list):
        return False
    return any(marker_text in (c.get("body") or "") for c in comments)


def _live_run_jobs(repo: str, run_id, now: datetime, errors: list[str]) -> dict | None:
    """The live re-read (proof 2): the run's status AND job rows at THIS moment."""
    p = _gh(["run", "view", str(run_id), "--repo", repo, "--json", "status,jobs"], timeout=60)
    if p.returncode != 0:
        errors.append(f"live re-read of run {run_id} ({p.returncode}): {(p.stderr or p.stdout).strip()[:240]}")
        return None
    try:
        data = json.loads(p.stdout)
    except json.JSONDecodeError:
        errors.append(f"live re-read of run {run_id}: unparseable answer: {p.stdout[:240]}")
        return None
    return data if isinstance(data, dict) else None


def _still_stalled(live: dict | None, f: dict, now: datetime) -> tuple[bool, str]:
    """Proofs 1+2 re-evaluated on the live re-read: still this watchdog's own stalled shape?

    Returns (cancellable, why-not). An unreadable re-read is NOT cancellable — the watchdog
    never cancels on stale data.
    """
    if live is None:
        return False, "live re-read failed — cancelling on stale data is refused"
    if str(live.get("status") or "").strip().lower() != "in_progress":
        return False, f"the run has already concluded ({live.get('status')})"
    rows = live.get("jobs") or []
    if not any(j.get("status") == "completed" for j in rows):
        return False, "no concluded sibling job on the live re-read"
    for j in rows:
        if str(j.get("id") or j.get("databaseId")) != str(f["job_id"]):
            continue
        if j.get("status") != "in_progress":
            return False, (f"job {f['job']!r} concluded between classification and cancel "
                           f"(conclusion {j.get('conclusion')}) — a live job is never touched")
        started = _iso_utc(j.get("startedAt")) or _iso_utc(live.get("runStartedAt"))
        if started is None:
            return False, f"job {f['job']!r} has no readable start on the live re-read"
        elapsed = _minutes(started, now)
        if elapsed <= f["budget"]:
            return False, (f"job {f['job']!r} reads {elapsed:.0f} min, at or under the "
                           f"{f['budget']:.0f} min budget on the live re-read")
        return True, ""
    return False, f"job {f['job']!r} is gone from the run on the live re-read"


def _cancel_stalled(repo: str, run_id, now: datetime) -> tuple[str, str]:
    """The cancel itself (proof 4). Returns (outcome, why-not): cancelled / race / failed.

    A cancel that races a conclusion is benign (the #1410 `--cancel-stranded` precedent:
    `gh run cancel` refuses runs GitHub already ended with a '...completed' answer).
    """
    p = _gh(["run", "cancel", str(run_id), "--repo", repo, "--force"], timeout=60)
    if p.returncode == 0:
        return "cancelled", ""
    err = (p.stderr or p.stdout).strip()
    if "completed" in err.lower():
        return "race", ""
    return "failed", f"run cancel for run {run_id} failed ({p.returncode}): {err[:240]}"


def _action_text(f: dict, outcome: str | None, why: str) -> str:
    """The paragraph the COMMENT states, naming the outcome the cancel actually produced."""
    if outcome == "cancelled":
        return ("Action: this watchdog CANCELLED the run (issue #2997 cancel policy — the class "
                "#2992 named but never cleared). A cancel ENDS a run and starts nothing: recovery "
                "arrives through GitHub events (push, PR synchronize, label) or a human. The "
                "`cancelled` conclusion reads through `ci_verdict.BLOCKING_CONCLUSIONS` and "
                "`auto_merge.RED_CONCLUSIONS`, so the head gets a classified verdict, not silence.")
    if outcome == "skipped":
        return (f"Action: cancel SKIPPED — {why}. The run is left running (the #1822/#1823 rule: "
                "a live job is never touched).")
    if outcome == "race":
        return ("Action: the cancel raced the run's conclusion (benign, the #1410 "
                "`--cancel-stranded` precedent) — GitHub had already ended the run.")
    if outcome == "failed":
        return (f"Action: the cancel FAILED — {why}. The run is left running; the lane reports the "
                "failure rather than pretending the wedge cleared.")
    return ("Named, not cancelled: `--cancel-stalled` (issue #2997 cancel policy) was not "
            "requested for this pass — cancellation requires the explicit knob.")


def _comment_body(f: dict, action: str) -> str:
    return (
        "stalled-job-watchdog: this run has a stalled `in_progress` job while its sibling jobs "
        f"already concluded (issue #2992 — the class that silenced the verdict and merge sweep for "
        f"26 minutes on run `44863652918`).\n\n"
        f"- job: **{f['job']}** (id `{f['job_id']}`) running **{f['elapsed']:.0f} min**, "
        f"budget **{f['budget']:.0f} min** = {f['derivation']}\n"
        f"- started: `{f['started']}` · run: {f['url']} "
        f"(branch `{f['branch']}` @ `{str(f['head_sha'])[:10]}`)\n\n"
        f"{action}\n"
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
    ap.add_argument("--cancel-stalled", action="store_true",
                    help="cancel each classified stalled PR-head run (the four proofs of issue "
                         "#2997; off by default — without it the watchdog names only, #2992)")
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
        if args.cancel_stalled:
            print(f"STALLED-JOB WATCHDOG: {len(findings)} stalled job(s) above; "
                  "--cancel-stalled is ON (the four proofs of issue #2997 gate every cancel).")
        elif findings:
            print(f"STALLED-JOB WATCHDOG: {len(findings)} stalled job(s) named above "
                  "(runs left running — `--cancel-stalled` (issue #2997) is the clearing knob).")
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
    n_cancelled = n_skipped = n_raced = 0
    for f in findings:
        pr, draft, is_open = (_pr_for_run(args.repo, f["head_sha"], now, errors)
                              if f["head_sha"] else (None, False, False))
        outcome, why = None, ""
        if args.cancel_stalled:
            # Cancel BEFORE filing so the comment states the outcome that actually happened.
            if pr is None:
                print(f"  run {f['run_id']} has no PR head — named only, never cancelled "
                      "(proof 3: no-PR runs stay the zero-job/frozen lanes' domain).")
            elif not is_open:
                print(f"  run {f['run_id']} head belongs to CLOSED PR #{pr} — named only, never "
                      "cancelled (proof 3: only OPEN non-draft PR heads are cancellable).")
            elif draft:
                print(f"  run {f['run_id']} head is DRAFT PR #{pr} — named only, never cancelled "
                      "(proof 3: only OPEN non-draft PR heads are cancellable).")
            else:
                live = _live_run_jobs(args.repo, f["run_id"], now, errors)
                cancellable, why = _still_stalled(live, f, now)
                if not cancellable:
                    outcome, why = "skipped", why
                    print(f"  run {f['run_id']} job {f['job']!r}: cancel SKIPPED — {why}")
                    n_skipped += 1
                else:
                    outcome, why = _cancel_stalled(args.repo, f["run_id"], now)
                    if outcome == "cancelled":
                        n_cancelled += 1
                        print(f"  CANCELLED run {f['run_id']} (job {f['job']!r} stalled past "
                              f"budget {f['budget']:.0f} min).")
                    elif outcome == "race":
                        n_raced += 1
                        print(f"  run {f['run_id']}: cancel raced the conclusion (benign, #1410).")
                    else:
                        failed += 1
                        print(f"  {why}", file=sys.stderr)
        if pr is None:
            print(f"  run {f['run_id']} belongs to no PR — named in this report only (no filing).")
            already_named += 1
            continue
        marker_text = f"{MARKER}: run {f['run_id']} job {f['job_id']}"
        if _already_commented(args.repo, pr, marker_text, now, errors):
            print(f"  run {f['run_id']} job {f['job']!r} already named on PR #{pr} — no second comment.")
            already_named += 1
            continue
        p = _gh(["issue", "comment", str(pr), "--repo", args.repo, "--body",
                 _comment_body(f, _action_text(f, outcome, why))])
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
    if args.cancel_stalled:
        print(f"STALLED-JOB CANCEL: {n_cancelled} cancelled, {n_skipped} skipped, {n_raced} raced "
              "(a cancel ends a run; nothing here dispatches, reruns, or re-triggers).")
    print(f"STALLED-JOB DELIVERY: {delivered} new comment(s), {already_named} already named, "
          f"{failed} failed.")
    return 3 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
