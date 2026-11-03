#!/usr/bin/env python3
"""Frozen-in-progress reaper: cancel + re-run a run that has not advanced for a long time (#1679).

A GitHub Actions run that hangs in_progress is invisible to BOTH existing healers: `ci-requeue.py`
re-runs only cancelled runs, and `run-failure-reactor.py` fires only on `conclusion: failure`. A run
stuck `in_progress` matches neither predicate, so it blocks the PR verdict indefinitely until a human
intervenes. Observed on #1671: an old head's `linux/unit` stalled in_progress, neither healer could
touch it (not cancelled, not failed), and the run only resolved when the branch moved on.

This reaper is the third, time-bounded trigger. It is deliberately SAFER than the other two:

  * It never cancels unless the run's `updated_at` is older than a threshold (default 90m) — a run
    that is still advancing (fresh `updated_at`) is never touched, and a run younger than the
    grace (default 15m) is never touched at all.
  * It only collapses runs that belong to an OPEN pull request — a push/schedule run is not a PR
    verdict and is left alone.
  * It posts the evidence (run id, both timestamps, PR, named owner) to the PR thread BEFORE it
    cancels anything, so the action is traceable the way a human's would be.
  * `--dry` / `DRY=1` / `plan` print the plan and touch nothing.

Commands (stdlib only, `gh` on PATH):

    ci_frozen_reaper.py plan [--threshold 90m] [--repo O/R]      the runs it WOULD cancel+re-run
    ci_frozen_reaper.py run  [--threshold 90m] [--repo O/R] [--dry]  cancel + re-run them (`--dry` prints only)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys

#: How old a run's `updated_at` must be (no advancement) before it is a frozen candidate.
DEFAULT_THRESHOLD = "90m"
#: A run younger than this is never touched (issue #1679 acceptance: does not fire within the first 15m).
GRACE_MINUTES = 15

_THRESHOLD_UNITS = {"m": "minutes", "h": "hours", "d": "days"}


def parse_threshold(text: str) -> dt.timedelta:
    """`90m` / `2h` -> a timedelta (the `--threshold` shape this repo uses)."""
    m = re.fullmatch(r"\s*(\d+)\s*([mhd])\s*", text or "")
    if not m:
        raise SystemExit(f"[frozen] bad --threshold {text!r}: use e.g. 90m, 2h, 1d")
    return dt.timedelta(**{_THRESHOLD_UNITS[m.group(2)]: int(m.group(1))})


def _gh(*args: str) -> str:
    """Run `gh` (the binary `CI_FROZEN_GH` names, so a test can drive a stub)."""
    exe = os.environ.get("CI_FROZEN_GH") or "gh"
    r = subprocess.run([exe, *args], capture_output=True, text=True)  # proc-allow: direct subprocess call site, tracked remainder for issue #797
    if r.returncode != 0:
        raise SystemExit(f"[frozen] {exe} {' '.join(args)} failed ({r.returncode}): {r.stderr.strip()}")
    return r.stdout


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _at(value: str | None) -> "dt.datetime | None":
    if not value:
        return None
    return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def in_progress_runs(repo: str) -> list[dict]:
    """Every run currently `in_progress` (any workflow), newest page first — bounded at 10 pages."""
    out: list[dict] = []
    page = 1
    while page <= 10:
        raw = _gh("api", f"repos/{repo}/actions/runs?per_page=100&status=in_progress&page={page}")
        runs = (json.loads(raw or "{}") or {}).get("workflow_runs") or []
        if not runs:
            break
        out.extend(runs)
        if len(runs) < 100:
            break
        page += 1
    return out


def _open_pull(repo: str, head_sha: str) -> dict | None:
    """The first OPEN pull whose head sha is `head_sha` (a push/schedule run is not a PR verdict)."""
    raw = _gh("api", f"repos/{repo}/commits/{head_sha}/pulls")
    for pr in (json.loads(raw or "{}") or []):
        if pr.get("state") == "open":
            return pr
    return None


def plan(repo: str, threshold: dt.timedelta, now: dt.datetime | None = None,
         grace_minutes: float = GRACE_MINUTES) -> tuple[list[dict], list[dict]]:
    """(runs to collapse, skipped with reason) — only old, non-advancing in_progress runs on open PRs."""
    now = now or _now()
    threshold_seconds = threshold.total_seconds()
    coll: list[dict] = []
    skipped: list[dict] = []
    for run in in_progress_runs(repo):
        rid = run.get("id")
        updated = _at(run.get("updated_at"))
        started = _at(run.get("run_started_at")) or _at(run.get("created_at"))
        if not updated or not started:
            skipped.append({**run, "why": "no timestamps (run not started)"})
            continue
        stale = (now - updated).total_seconds()
        age = (now - started).total_seconds()
        if age < grace_minutes * 60:
            skipped.append({**run, "why": f"younger than the {grace_minutes:.0f}m grace"})
            continue
        if stale <= threshold_seconds:
            skipped.append({**run, "why": "still advancing (updated_at newer than the threshold)"})
            continue

        # Hidden from the repo API when there is no open PR at the head.
        pr = None
        try:
            pr = _open_pull(repo, str(run.get("head_sha")))
        except SystemExit:
            pr = None
        if pr is None:
            skipped.append({**run, "why": "no open PR at this head (push/schedule run is not a PR verdict)"})
            continue

        owner = (pr.get("user") or {}).get("login") or (pr.get("author") or {}).get("login") or "unknown"
        coll.append({**run,
                     "stale_minutes": round(stale / 60.0, 1),
                     "age_minutes": round(age / 60.0, 1),
                     "pr_number": pr.get("number"),
                     "pr_url": pr.get("html_url"),
                     "owner": owner,
                     "head_sha": str(run.get("head_sha")),
                     "head_branch": str(run.get("head_branch"))})
    return coll, skipped


def _comment(repo: str, pr_number: int, body: str, dry: bool) -> None:
    if dry:
        print(f"[frozen] DRY would comment on PR #{pr_number}: {body[:80]}...")
        return
    _gh("api", f"repos/{repo}/issues/{pr_number}/comments", "-f", f"body={body}")


def _cancel_and_rerun(repo: str, run_id: int, dry: bool) -> None:
    if dry:
        print(f"[frozen] DRY would cancel + re-run run {run_id}")
        return
    _gh("run", "cancel", str(run_id), "--repo", repo)
    _gh("run", "rerun", str(run_id), "--repo", repo)
    print(f"[frozen] cancelled + re-ran run {run_id}")


def _evidence(run: dict) -> str:
    return (f"BOT ci-frozen-reaper — run `{run['id']}` on PR #{run['pr_number']} "
            f"({run['pr_url']}) has been `in_progress` without advancing for "
            f"{run['stale_minutes']}m (updated_at stale; run age {run['age_minutes']}m). "
            f"Owner: `@{run['owner']}`. Head `{run['head_sha'][:7]}` branch `{run['head_branch']}`. "
            f"Cancelling and re-running this one frozen run so the PR can get a verdict.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Cancel + re-run a frozen in_progress run (issue #1679)")
    ap.add_argument("cmd", choices=("plan", "run"))
    ap.add_argument("--repo", default="asimov-agent/llgenie")
    ap.add_argument("--threshold", default=DEFAULT_THRESHOLD,
                    help=f"how long a run may be in_progress without advancing (default {DEFAULT_THRESHOLD})")
    ap.add_argument("--dry", action="store_true", help="cancel/re-run nothing, print the plan")
    a = ap.parse_args(argv)

    threshold = parse_threshold(a.threshold)
    freezing, kept = plan(a.repo, threshold)
    for run in freezing:
        _comment(a.repo, run["pr_number"], _evidence(run), dry=a.dry or a.cmd == "plan")
        _cancel_and_rerun(a.repo, run["id"], dry=a.dry or a.cmd == "plan")
    for run in kept:
        print(f"[frozen] keep {run['id']} "
              f"{(run.get('head_branch') or '')}@{str(run.get('head_sha'))[:7]} - {run['why']}")
    verb = "would collapse" if (a.dry or a.cmd == "plan") else "collapsed"
    print(f"[frozen] {verb} {len(freezing)} frozen run(s); left {len(kept)} alone")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
