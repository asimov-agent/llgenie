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

Exit codes: 0 = no STRANDED zero-job run (queued-behind zero-job runs are benign), 1 = at least one
stranded, 2 = the GitHub read failed.

THE DISCRIMINATOR (issue #1704): `jobs.total_count == 0` alone is NOT a "no runner matched" claim.
`engine-build` serialises every build per `engine × arch` concurrency group (#917,
`cancel-in-progress: false`), so a `workflow_dispatch` run queued behind a sibling holding the same
group reads `queued`, zero jobs, past the threshold — but it is QUEUEING, not stranded, and six
consecutive filings mis-named it as "no runner matched labels" (#1473/#1536/#1569/#1699/#1700/#1701,
all true false positives). A run is only the genuine #1410 case when its concurrency group is FREE —
no same-workflow run is `in_progress` holding it — AND the zero jobs persist. This module classifies
each zero-job run, keeps the queued-behind ones out of the report, files only the stranded ones, and
FORCES a stranded run's head RED via the `ci-verdict` check-run path (a `pending` run has no decision,
and no-decision is already red — see `scripts/ci_scope.py::verify`), so a truly-unrunnable dispatch
surfaces as a failed check with a reason instead of an eternal `pending` that reads like a working
matrix (#1704). The monitor workflow carries `checks: write` so the RED check-run can land.

CLEARING, not just naming (`--cancel-stranded`): naming a stranded run once and then skipping it on
every later monitor run (the already-filed dedupe) leaves the zombie `pending` forever — GitHub does
not evict a zero-job run by itself, and the original #1410 case was ended only by a manual cancel.
Measured 2026-11-12: the 08:23 monitor filing named five runs (issues #2520-#2525) created 2026-11-11
20:33Z/20:47Z on branches whose PRs (#2500, #2507) merged that same evening; twelve hours later four
were STILL `queued` with zero jobs and `updated_at` frozen at creation, and `gh run cancel` refused
them claiming they were "completed" while the run list still showed `queued`. Meanwhile a live
engine-build job (43149786553 `engine-build-strata-cuda`) waited ~7h behind them for a runner. So with
`--cancel-stranded` the monitor CANCELS each stranded run — including already-filed ones (the dedupe
covers filing/RED only) — after re-reading the run's jobs: a run whose jobs instantiated since
classification (a runner finally arrived) is SKIPPED, never cancelled (the #1822/#1823 live-compile
class). A cancel that races a conclusion ("...is completed") is benign, not a delivery failure.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ci_scope  # noqa: E402  the verdict grammar + the check-run payload this monitor posts
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
    """Runs in this repo still `queued`/`in_progress` with zero jobs, past `minutes`.

    A zero-job run is STRANDED when no sibling of the same workflow+branch is currently `in_progress`
    with the same concurrency intent — it should have got a runner and did not (issue #1410). It is
    QUEUED when a sibling is already running the same (workflow, branch) pair: engine-build serialises
    per engine×arch concurrency group (#917) and the later dispatch legally waits with zero jobs until
    its turn. The discriminator keeps a queued run OUT of the report so "no runner matched the labels"
    is never filed for a run that is simply waiting its turn — the 6/6-false-positive reactor class
    (#1704).
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    seen: set[int] = set()
    candidates: list[dict] = []
    in_progress: set[tuple[str, str]] = set()
    for status in ("queued", "in_progress"):
        runs = json.loads(_gh(["run", "list", "--repo", repo, "--status", status,
                               "--limit", str(limit),
                               "--json", "databaseId,workflowName,headBranch,headSha,createdAt,url,status"])
                          or "[]")
        for run in runs:
            rid = run.get("databaseId")
            if rid is None or rid in seen:
                continue
            seen.add(rid)
            if status == "in_progress":
                # A currently-running sibling is the concurrency holder: anything else with the same
                # (workflow, branch) is queued behind it, not stranded.
                in_progress.add((run.get("workflowName", ""), run.get("headBranch", "")))
            candidates.append(run)
    out: list[dict] = []
    for run in candidates:
        key = (run.get("workflowName", ""), run.get("headBranch", ""))
        # A QUEUED run behind an in_progress sibling that holds the same concurrency group is waiting
        # its turn, not short of runners — the benign #917 serialisation case (#1704). An IN_PROGRESS
        # run with zero jobs is itself the stalled one: it took the group and still instantiated
        # nothing, so it stays a candidate. This key is computed before the jobs read so the queued
        # skip never pays a `run view` round-trip.
        if run.get("status") == "queued" and key in in_progress:
            continue
        rid = run.get("databaseId")
        jobs = json.loads(_gh(["run", "view", str(rid), "--repo", repo, "--json", "jobs"]) or "{}")
        # `gh run view --json jobs` returns `{"jobs":[...]}` — the jobs ARRAY, with NO `total_count`
        # key (measured 2026-11-06: run 42141213441 reported 3 live jobs, the key was absent). Counting
        # the array is the honest total: a run whose jobs array is non-empty has instantiated jobs and is
        # NOT this monitor's zero-job case, however long it has run (a live 2h compile must never be
        # named a "no runner matched" false positive — the #1822/#1823 class).
        total = len((jobs.get("jobs") if isinstance(jobs, dict) else None) or [])
        if total != 0:
            continue
        age = _age_minutes(run.get("createdAt"), now)
        if age is None or age < minutes:
            continue
        out.append({"run": rid,
                    "workflow": run.get("workflowName", ""),
                    "branch": run.get("headBranch", ""),
                    "head": (run.get("headSha") or "")[:12],
                    "head_sha": (run.get("headSha") or ""),
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


def already_filed(repo: str, rid: int) -> bool:
    """Has run `rid` already been reported (its dedupe marker is in an open issue's body)?"""
    try:
        found = json.loads(_gh(["issue", "list", "--repo", repo, "--state", "open",
                                "--search", f"{rid} in:body", "--json", "body"]) or "[]")
    except (RuntimeError, ValueError):
        return False
    return any(_run_marker(rid) in (i.get("body") or "") for i in found)


def _how_steps(r: dict, cancel_action: tuple[str, str] | None) -> list[str]:
    """`How we fix it` for a per-run zombie issue, honest about what the monitor actually did.

    With `--cancel-stranded` the cancel runs BEFORE filing, so the body states the real outcome
    (cancelled / skipped-because-a-runner-arrived / already-concluded-race / failed) instead of a
    promise the monitor may not have kept. Without the flag, only the manual steps are named.
    """
    rid = r["run"]
    action, why = cancel_action or ("", "")
    steps: list[str] = []
    if action == "cancelled":
        steps.append(
            f"Automatic remedy (monitor with `--cancel-stranded`): run {rid} has **already been "
            "cancelled** — the monitor re-read its jobs first, so a run whose runner finally "
            "arrived would have been skipped, never killed. GitHub does not evict a zero-job run "
            "by itself, and naming one without clearing it leaves the zombie in the queue starving "
            "live work (measured 2026-11-12: named 08:23Z, still queued 12:19Z)."
        )
    elif action == "skipped":
        steps.append(
            f"Automatic remedy: the monitor's cancel was **skipped** — {why}. The run got its "
            "runner at cancel time and is no longer a zero-job run."
        )
    elif action == "already":
        steps.append(
            f"Automatic remedy: the cancel raced a conclusion — GitHub had already ended run {rid} "
            "before the cancel was issued; nothing is left pending."
        )
    elif action == "failed":
        steps.append(
            f"Automatic remedy FAILED: {why} — the cancel did not land; a manual "
            f"`gh run cancel {rid} --force` is required."
        )
    steps.append("Match a runner to the requested labels (a self-hosted runner is offline/unregistered, "
                 "or the account's hosted-runner capacity for that OS is exhausted).")
    steps.append("Re-dispatch the run (or the workflow it belongs to) once a runner exists — a cancelled "
                 "zero-job run does not restart by itself.")
    return steps


def file_one_issue(repo: str, r: dict, body: str, dry: bool = False,
                   cancel_action: tuple[str, str] | None = None) -> str:
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
        how=_how_steps(r, cancel_action),
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


def force_red_verdict(repo: str, r: dict) -> str:
    """Force a stranded run's head RED via the `ci-verdict` check-run path; "" on success.

    A `pending`/`queued` zero-job run publishes no scope decision — and `scripts/ci_scope.py::verify`
    reds "no decision" (a skipped selected job OR no decision is already red). But the run never
    COMPLETES, so `ci-verdict`'s own `workflow_run: [completed]` hook never fires on it. This posts the
    same `ci-verdict` check-run payload the verdict would post, so a runner-starvated head that never
    completes still surfaces as a FAILED check with a reason instead of an eternal `pending`.
    Idempotent: posting the same check-run name again just updates it (the check already exists after
    the first filing). Returns the failure reason otherwise, so delivery is loud (#294).
    """
    head = (r.get("head_sha") or "")
    if not head:
        return f"run {r['run']} has no head sha — cannot force the verdict check-run"
    lines = [
        f"[zero-job-pending] run {r['run']} {r['workflow']} head={head[:7]} conclusion=pending "
        f"(#1704)",
        f"[zero-job-pending] ZERO JOBS past the threshold on a FREE concurrency group — no runner matched",
        f"[zero-job-pending] verdict=red success=0 failure=0 skipped-by-decision=0 no-verdict=1 pending=0",
        f"[zero-job-pending] NO VERDICT: a zero-job pending run has no decision — 0 failures is not a verdict",
    ]
    payload = ci_scope.check_run_payload(ci_scope.RED, head, lines,
                                         run_label=f"zero-job run {r['run']} (#1704)")
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(payload, f)
        path = f.name
    rq = run_ok(["gh", "api", f"repos/{repo}/check-runs", "--method", "POST", "--input", path])
    Path(path).unlink(missing_ok=True)
    if rq.returncode != 0:
        return f"check-run for run {r['run']} failed ({rq.returncode}): {rq.stderr.strip()}"
    return ""


def cancel_stranded(repo: str, r: dict) -> tuple[str, str]:
    """Clear one stranded zero-job run; returns (action, reason).

    action: "cancelled" (run cancel landed), "skipped" (the jobs re-read found instantiated jobs — a
    runner finally arrived after classification, so this is not ours to kill: the #1822/#1823 class —
    reason names it), "already" (the cancel raced a conclusion: GitHub reports the run completed; the
    run is no longer live and the next scan will not name it), "failed" (reason names the failure —
    delivery must stay loud, #294).

    The jobs re-read is the safety gate: classification read jobs once; a stranded verdict made at
    30 minutes must not cancel a build that got a runner at minute 31. Re-reading at the moment of
    cancelling is what keeps the #917 "never cancel a live compile" rule true across the gap.
    """
    rid = r["run"]
    try:
        jobs = json.loads(_gh(["run", "view", str(rid), "--repo", repo, "--json", "jobs"]) or "{}")
    except RuntimeError as e:
        return "failed", f"jobs re-read for run {rid} failed: {e}"
    total = len((jobs.get("jobs") if isinstance(jobs, dict) else None) or [])
    if total != 0:
        return "skipped", (f"run {rid}: {total} job(s) instantiated since classification — "
                           f"a live run is never cancelled")
    rq = run_ok(["gh", "run", "cancel", str(rid), "--repo", repo, "--force"])
    if rq.returncode != 0:
        err = (rq.stderr or "").strip()
        if "completed" in err:
            return "already", ""
        return "failed", f"run cancel for run {rid} failed ({rq.returncode}): {err}"
    return "cancelled", ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Flag dispatched runs pending/queued too long with zero jobs")
    ap.add_argument("--repo", required=True, help="owner/repo")
    ap.add_argument("--minutes", type=float, default=30.0, help="threshold minutes (default 30)")
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--file", action="store_true",
                    help="force every stranded run's head RED via ci-verdict and file ONE deduped "
                         "issue per stranded run (idempotent by run-id marker)")
    ap.add_argument("--cancel-stranded", action="store_true",
                    help="cancel every stranded run, INCLUDING already-filed ones (the marker dedupe "
                         "covers filing/RED only); the jobs are re-read at the moment of cancelling "
                         "and a run that instantiated jobs since classification is skipped, never "
                         "cancelled")
    args = ap.parse_args(argv)
    try:
        rows = zero_job_pending_runs(args.repo, minutes=args.minutes, limit=args.limit)
    except RuntimeError as e:
        print(f"[{MARKER}] github read failed: {e}", file=sys.stderr)
        return 2
    print(render(rows, args.minutes))
    if not rows:
        return 0
    if args.file or args.cancel_stranded:
        failures: list[str] = []
        skipped: list[str] = []
        n_filed = n_red = 0
        n_cancelled = n_skipped = n_already = 0
        for r in rows:
            rid = r["run"]
            # Clear first, name second: with --cancel-stranded the cancel is attempted BEFORE the
            # issue is written, so the body states the outcome that actually happened (cancelled /
            # skipped because a runner arrived / raced a conclusion / failed) rather than a promise.
            # The jobs re-read inside cancel_stranded is the safety gate — a run that instantiated
            # jobs since classification is never touched (the #1822/#1823 live-compile class).
            cancel_action: tuple[str, str] | None = None
            if args.cancel_stranded:
                cancel_action = cancel_stranded(args.repo, r)
                action, why = cancel_action
                if action == "cancelled":
                    n_cancelled += 1
                elif action == "skipped":
                    n_skipped += 1
                    skipped.append(why)
                elif action == "already":
                    n_already += 1
                else:
                    failures.append(why)
            # Named once: a run already reported (its marker in an open issue) is not delivered a
            # second time — neither re-filed nor re-forced RED. A fresh stranded run gets exactly one
            # delivery: force its head RED (so the same gates that catch every other red catch this
            # one) AND file the one deduped issue naming it. The dedupe guards NAMING only: an
            # already-filed run is still a zombie today, so --cancel-stranded clears it regardless.
            if args.file and not already_filed(args.repo, rid):
                why_red = force_red_verdict(args.repo, r)
                why_file = file_one_issue(args.repo, r, render([r], args.minutes),
                                          cancel_action=cancel_action)
                n_red += 0 if why_red else 1
                n_filed += 0 if why_file else 1
                for why in (why_red, why_file):
                    if why:
                        failures.append(why)
        if failures:
            for why in failures:
                print(f"[{MARKER}] DELIVERY FAILED: {why}", file=sys.stderr)
            return 3
        if args.file:
            print(f"[{MARKER}] filed {n_filed} deduped issue(s) and forced "
                  f"{n_red} stranded run(s) RED", flush=True)
        if args.cancel_stranded:
            print(f"[{MARKER}] cancelled {n_cancelled} stranded run(s), {n_already} already "
                  f"concluded, skipped {n_skipped} (jobs instantiated since classification)",
                  flush=True)
            for why in skipped:
                print(f"[{MARKER}] cancel skipped: {why}", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
