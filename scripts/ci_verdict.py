#!/usr/bin/env python3
"""A finished CI run's verdict: the jobs that reported, held to the decision that selected them (#1111).

A run that was CANCELLED and a run that ran look almost identical from a check-runs listing, and that
is the defect this file answers. Measured 2026-10-30 on run 41134761297 (`CI`, head `0bd5ac6e`,
conclusion `cancelled`):

    guard success · ci-images cancelled · scanner-images cancelled · linux skipped
    => success=3, failed=0, other=5, pending=0

No `linux / unit` row existed at all — the unit gate never ran — and every reader that quotes a
failure count read that head as clean: `0 failures` is what the summary line said, and it was armed
with no unit verdict. The same class of change at `d92ee6a3` (run 41126873965) had the full set with
`linux / unit failure`, so one head proved the change was wrong and the next head proved nothing.

What was missing is not a conclusion, it is a DECISION: `scripts/ci_scope.py` decides which jobs a
diff selects, `ci.yml`'s `guard` job publishes that decision as the `ci-scope-decision` artifact, and
this tool reads it back against the finished run:

  * a job the decision selected that reported `skipped`, `cancelled`, or not at all -> `no_verdict`
    (red) — a gate that never ran is not a gate that passed;
  * a job the decision did NOT select that is skipped -> `skipped_by_decision` (green) — the
    legitimate skip, now named and counted;
  * NO decision on the run at all -> `verdict=none`, red, because nobody decided and "0 failures" is
    not a verdict.

SUPERSEDED is the one case that is not red: `ci.yml` sets `cancel-in-progress` on a pull request, so
every push cancels the run above it, and a cancelled run that a LATER run of the same workflow on the
same branch already replaced is owed nothing — that head's verdict belongs to the newer run. The
check-run is posted `neutral` there, never `success`, so a superseded head still never reads as a
pass. It is the same test `scripts/ci_requeue.py` uses to decide what to re-run.

Why post a check-run at all: a `workflow_run` run creates NO check-run of its own on the commit
(measured on `0bd5ac6e`: the cancelled CI run's rows are the only ones, `auto-merge`'s own run is
absent), so a verdict that only reds its own workflow would be invisible to every check-run reader.
`--check-run-out` writes the `POST /repos/{owner}/{repo}/check-runs` body; the workflow posts it.

The accounting lives in `scripts/ci_scope.py::verify()` (the module that owns the job table), so the
grammar is one place and the network is another.

Commands (stdlib only, `gh` on PATH — `CI_VERDICT_GH` names the binary a test drives instead):

    ci_verdict.py --repo O/R --run-id <id> [--check-run-out FILE]   a finished run, read from GitHub
    ci_verdict.py --jobs FILE [--decision FILE] [--head-sha SHA]    the same decision, from files

Exit codes:
    0  green, or neutral because a later run of the same workflow owns this head
    1  red: a selected job is missing/skipped/cancelled, a job failed, or the run has no decision
    2  the verdict could not be reached (an API call failed, an unreadable artifact): never a pass
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ci_scope  # noqa: E402

TAG = "[ci-verdict]"

#: The artifact `ci.yml`'s `guard` job uploads, and the verdict reads back.
ARTIFACT = "ci-scope-decision"

#: The check-run name a reader looks for. It is not derived from a job name on purpose: it must be the
#: same string on a run whose jobs do not exist, which is exactly when it matters most.
CHECK_NAME = "ci-verdict"

EXIT_GREEN = 0
EXIT_RED = 1
EXIT_ERROR = 2


def _gh(*args: str) -> str:
    """Run `gh` (the binary `CI_VERDICT_GH` names, so a test can drive a stub — as `ci_requeue` does)."""
    exe = os.environ.get("CI_VERDICT_GH") or "gh"
    result = subprocess.run([exe, *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"{exe} {' '.join(args)} failed ({result.returncode}): {result.stderr.strip()}")
    return result.stdout


def _api(path: str) -> dict:
    return json.loads(_gh("api", path) or "{}")


def run_info(repo: str, run_id: str) -> dict:
    """The run itself: conclusion, head sha, branch, workflow — what the verdict has to name."""
    return _api(f"repos/{repo}/actions/runs/{run_id}")


def jobs_of(repo: str, run_id: str) -> list[dict]:
    """Every job row of the run (one page of 100; the fan-out is ten job names, see `ci_scope.JOBS`)."""
    payload = _api(f"repos/{repo}/actions/runs/{run_id}/jobs?per_page=100")
    jobs = payload.get("jobs") or []
    if int(payload.get("total_count") or 0) > len(jobs):
        raise RuntimeError(
            f"run {run_id} reports {payload.get('total_count')} job(s) and one page returned {len(jobs)}: "
            f"a truncated listing cannot be a verdict")
    return jobs


def decision_of(repo: str, run_id: str) -> dict | None:
    """The published decision, or None when the run published none.

    A MISSING artifact is a verdict (`none`), never an error: a cancelled run is precisely a run that
    may never have reached the step that writes it. An artifact that EXISTS but cannot be read is an
    error (exit 2) — a transport failure must not be dressed up as "nobody decided".
    """
    listing = _api(f"repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100")
    names = {str(a.get("name")) for a in listing.get("artifacts") or []}
    if ARTIFACT not in names:
        print(f"{TAG} no `{ARTIFACT}` artifact on run {run_id} — this run published no decision")
        return None
    with tempfile.TemporaryDirectory() as directory:
        _gh("run", "download", str(run_id), "--repo", repo, "-n", ARTIFACT, "-D", directory)
        path = Path(directory) / f"{ARTIFACT}.json"
        if not path.is_file():
            raise RuntimeError(f"artifact `{ARTIFACT}` downloaded from run {run_id} holds no {ARTIFACT}.json")
        payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != ci_scope.DECISION_SCHEMA:
        raise RuntimeError(
            f"run {run_id}'s decision is schema {payload.get('schema')!r}; this verdict reads "
            f"{ci_scope.DECISION_SCHEMA} — a decision it cannot read is not a verdict")
    return payload


def superseding_run(repo: str, run: dict) -> dict | None:
    """The later run of the SAME workflow on the SAME branch, or None — `ci_requeue`'s supersede test.

    Judged per (workflow, branch), never per `head_sha`: another workflow on the same commit (`scope`,
    `holds`) is not a newer verdict for THIS one, and `ci.yml`'s `cancel-in-progress` leaves exactly
    that shape behind on every push.
    """
    branch = run.get("head_branch")
    workflow_id = run.get("workflow_id")
    created = run.get("created_at")
    if not branch or not created:
        return None
    listing = _api(f"repos/{repo}/actions/runs?branch={branch}&per_page=50")
    later = [other for other in listing.get("workflow_runs") or []
             if other.get("workflow_id") == workflow_id
             and str(other.get("created_at") or "") > str(created)]
    return sorted(later, key=lambda r: str(r.get("created_at")))[-1] if later else None


def verdict_lines(result: dict, run: dict | None, superseding: dict | None) -> list[str]:
    """The decision report plus the run it is about — one line per finding, the summary last."""
    header: list[str] = []
    if run:
        header.append(
            f"{TAG} run {run.get('id')} {run.get('name') or ''} head={str(run.get('head_sha'))[:7]} "
            f"conclusion={run.get('conclusion') or run.get('status')}")
    lines = header + result["lines"]
    if superseding is not None:
        lines.append(
            f"{TAG} SUPERSEDED by run {superseding.get('id')} "
            f"({superseding.get('conclusion') or superseding.get('status')}) on "
            f"{superseding.get('head_branch')} — a later run of this workflow owns this head, so the "
            f"conclusion posted below is neutral, never success")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Hold a finished CI run to its scope decision (#1111).")
    parser.add_argument("--repo", default=os.environ.get("REPO") or "asimov-agent/llgenie")
    parser.add_argument("--run-id", default=os.environ.get("RUN_ID"),
                        help="the finished run to judge (default: $RUN_ID)")
    parser.add_argument("--jobs", default=os.environ.get("CI_VERDICT_JOBS"),
                        help="read the job rows from this file instead of the API (a test, a replay)")
    parser.add_argument("--decision", default=os.environ.get("CI_VERDICT_DECISION"),
                        help="read the decision from this file instead of the artifact")
    parser.add_argument("--head-sha", default=os.environ.get("HEAD_SHA"),
                        help="the commit the verdict is about (default: the run's head sha)")
    parser.add_argument("--check-run-out", default=os.environ.get("CHECK_RUN_OUT"),
                        help="write the POST /check-runs body to this file")
    args = parser.parse_args(argv)

    if not args.run_id and not args.jobs:
        print(f"{TAG} FAILED: give --run-id (a finished run) or --jobs (a file of job rows)", file=sys.stderr)
        return EXIT_ERROR

    try:
        run = run_info(args.repo, args.run_id) if args.run_id else None
        jobs = (json.loads(Path(args.jobs).read_text(encoding="utf-8"))
                if args.jobs else jobs_of(args.repo, args.run_id))
        if isinstance(jobs, dict):
            jobs = jobs.get("jobs") or []
        if args.decision:
            decision_obj = json.loads(Path(args.decision).read_text(encoding="utf-8"))
            if decision_obj.get("schema") != ci_scope.DECISION_SCHEMA:
                raise RuntimeError(
                    f"{args.decision} is schema {decision_obj.get('schema')!r}, this verdict reads "
                    f"{ci_scope.DECISION_SCHEMA}")
        elif args.run_id:
            decision_obj = decision_of(args.repo, args.run_id)
        else:
            decision_obj = None
        superseding = superseding_run(args.repo, run) if run else None
    except (RuntimeError, OSError, json.JSONDecodeError) as exc:
        # Never a pass: a verdict that could not be reached is reported as its own failure.
        print(f"{TAG} FAILED: could not reach a verdict — {exc}", file=sys.stderr)
        return EXIT_ERROR

    result = ci_scope.verify(decision_obj, jobs)
    lines = verdict_lines(result, run, superseding)
    for line in lines:
        print(line)

    head_sha = args.head_sha or (run or {}).get("head_sha") or ""
    if result["verdict"] == ci_scope.GREEN:
        conclusion, code = "success", EXIT_GREEN
    elif superseding is not None:
        conclusion, code = "neutral", EXIT_GREEN
    else:
        conclusion, code = "failure", EXIT_RED

    if args.check_run_out:
        payload = ci_scope.check_run_payload(
            result["verdict"], head_sha, lines, conclusion=conclusion,
            run_label=f"run {args.run_id}" if args.run_id else "replay")
        payload["name"] = CHECK_NAME
        Path(args.check_run_out).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"{TAG} check-run payload -> {args.check_run_out} (conclusion={conclusion})")

    if code == EXIT_RED:
        print(f"{TAG} FAILED: run {(run or {}).get('id') or '-'} has no verdict — "
              f"see the summary line above, which is what a board must quote instead of a failure count",
              file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
