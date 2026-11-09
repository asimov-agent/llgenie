#!/usr/bin/env python3
"""Re-run the CI runs a bulk cancel killed, so a killed PR gets a verdict again (issue #843).

Freeing the runner queue by cancelling runs is a legitimate lever, and it has one missing half:
a cancelled run is not a verdict, but every reader treats it as final. `gh pr checks` renders
`completed/cancelled` as **fail**, `auto-merge` needs a green run, `run-failure-reactor` fires only
on `conclusion: failure` and `fix-bot` reacts only to red checks — so a cancelled run leaves a PR
with a check nobody owns, and nothing re-dispatches it.

Measured on 2026-10-28: 168 of the last 300 runs were `cancelled` (56 %), and on each of four open
PRs the cancelled run was the ONLY run on its head sha — not `ci.yml`'s `cancel-in-progress`, which
leaves a successor on a newer commit.

This target is the healer, and it is deliberately narrow: it re-runs a cancelled run ONLY when no
later run of the SAME workflow exists on that branch. A run that a newer commit superseded is left
alone — re-running it would burn the runners on a verdict that a later run already owns.

Commands (stdlib only, `gh` on PATH):

    ci_requeue.py plan [--window 2h] [--repo O/R]        the runs it WOULD re-run, and why not others
    ci_requeue.py run  [--window 2h] [--repo O/R] [--dry]  re-run them (`--dry` prints only)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys

#: The default window: how far back a kill is still worth healing. A day-old cancellation has been
#: superseded by the author or the next commit in practice, and a wide window would re-run history.
DEFAULT_WINDOW = "2h"

_WINDOW_UNITS = {"m": "minutes", "h": "hours", "d": "days"}

#: The stderr shapes `gh run rerun` emits when GitHub REFUSES a retry — a decision, not a
#: transient failure (issue #2295). A run whose workflow was deleted, whose artefacts expired,
#: or whose conclusion GitHub will not re-open answers this way every time; retrying the sweep
#: can never clear it, so the healer records it as SKIPPED (never failed) and moves on. Any
#: other non-zero gh return — rate limit, 5xx, auth — is a transient/real failure and STAYS
#: fatal (the negative control: a real problem must not be swallowed).
NON_RETRYABLE_MARKERS = ("cannot be retried", "cannot be rerun")


def parse_window(text: str) -> dt.timedelta:
    """`2h` / `90m` / `1d` -> a timedelta (the shape every `--window` in this repo takes)."""
    m = re.fullmatch(r"\s*(\d+)\s*([mhd])\s*", text or "")
    if not m:
        raise SystemExit(f"[requeue] bad --window {text!r}: use e.g. 90m, 2h, 1d")
    return dt.timedelta(**{_WINDOW_UNITS[m.group(2)]: int(m.group(1))})


def _gh(*args: str) -> str:
    """Run `gh` (the binary `CI_REQUEUE_GH` names, so a test can drive a stub)."""
    exe = os.environ.get("CI_REQUEUE_GH") or "gh"
    r = subprocess.run([exe, *args], capture_output=True, text=True)  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
    if r.returncode != 0:
        raise SystemExit(f"[requeue] {exe} {' '.join(args)} failed ({r.returncode}): {r.stderr.strip()}")
    return r.stdout


def _gh_no_raise(*args: str) -> tuple[int, str]:
    """Run `gh`, returning (returncode, stderr) instead of aborting — the probe a rerun needs.

    `rerun()` must tell GitHub's *refusal* to retry from a *transient* failure (issue #2295): a
    run GitHub will not retry is a decision and must not red the sweep, so it is returned here for
    classification; every other non-zero return is a real problem and stays fatal.
    """
    exe = os.environ.get("CI_REQUEUE_GH") or "gh"
    r = subprocess.run([exe, *args], capture_output=True, text=True)  # proc-allow: direct subprocess call site, tracked remainder for issue #797 (migrate onto scripts/proc.py in a per-module batch)
    return r.returncode, r.stderr.strip()


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def completed_runs(repo: str, window: dt.timedelta, now: dt.datetime | None = None) -> list[dict]:
    """Every COMPLETED run created inside the window, of any conclusion.

    All conclusions, not only `cancelled`: supersession is decided by a LATER run of the same workflow
    on the same branch, and that later run is usually a success — filtering the listing to cancellations
    first would make every cancelled run look like the newest and heal what a push already fixed.
    """
    cutoff = (now or _now()) - window
    out: list[dict] = []
    page = 1
    while page <= 10:                       # bounded: 10 pages of 100 is plenty for any window
        raw = _gh("api", f"repos/{repo}/actions/runs?per_page=100&status=completed&page={page}")
        runs = (json.loads(raw or "{}") or {}).get("workflow_runs") or []
        if not runs:
            break
        oldest = None
        for r in runs:
            created = dt.datetime.fromisoformat(str(r.get("created_at")).replace("Z", "+00:00"))
            oldest = created if oldest is None else min(oldest, created)
            if created < cutoff:
                continue
            out.append(r)
        if oldest is not None and oldest < cutoff:
            break
        page += 1
    return out


def _job_count(repo: str, run: dict) -> int:
    """How many jobs a run instantiated (`total_count`) — 0 for a cancelled run means GitHub
    will refuse `gh run rerun --failed` with "This workflow run cannot be retried" (nothing to
    retry; measured on the engine-build dispatch run #2295). Deterministic and cheap, so `plan`
    can classify a non-retryable run WITHOUT dispatching a rerun (the DRY classifier).
    """
    try:
        raw = _gh("api", f"repos/{repo}/actions/runs/{run['id']}/jobs?per_page=100")
    except SystemExit:
        return -1                                 # unknown: don't guess, let the runtime classify
    return int((json.loads(raw or "{}") or {}).get("total_count", -1))


def plan(repo: str, window: dt.timedelta, now: dt.datetime | None = None) -> tuple[list[dict], list[dict]]:
    """(the runs to re-run, the ones passed over with the reason) for one window.

    Supersession is judged from the RUN LISTING, per workflow and branch: a cancelled run is
    superseded when a later run of the SAME workflow on the SAME branch exists. Judging it per
    `head_sha` instead is both slower (one API call per run) and wrong — another workflow on the same
    commit (`scope`, `docs`) is not a newer verdict for this one, and on a PR that runs both, every
    cancelled CI run would look superseded and never be healed.

    A cancelled `workflow_run`-triggered run is NEVER requeued: a reaction run (`auto-merge`,
    `ci-verdict`, `run-failure-reactor`) is a completion GitHub will not retry (`gh run rerun` rejects
    it with "This workflow run cannot be retried", #1451), so re-running it would abort the whole heal
    after the first one. Such a run lands in the SKIPPED list with the reason, so `plan --dry` names
    it instead of passing it over silently (#286-adjacent: the reactor already special-cases its own
    `workflow_run` origin).
    """
    runs = completed_runs(repo, window, now)
    newest: dict[tuple, dt.datetime] = {}
    max_attempt: dict[tuple, int] = {}
    for run in runs:                       # the listing is not sorted; take the max per (workflow, branch)
        key = (run.get("workflow_id"), run.get("head_branch"))
        created = dt.datetime.fromisoformat(str(run.get("created_at")).replace("Z", "+00:00"))
        newest[key] = max(newest.get(key, created), created)
        max_attempt[key] = max(max_attempt.get(key, 0), int(run.get("run_attempt") or 1))
    requeue: list[dict] = []
    skipped: list[dict] = []
    for run in runs:
        if run.get("conclusion") != "cancelled":
            continue
        if run.get("event") == "workflow_run":
            skipped.append({**run, "why": "workflow_run-triggered: GitHub will not retry this run"})
            continue
        key = (run.get("workflow_id"), run.get("head_branch"))
        created = dt.datetime.fromisoformat(str(run.get("created_at")).replace("Z", "+00:00"))
        # A re-run of the same run id keeps `created_at` and bumps only `run_attempt` (#1250 Finding A):
        # a cancelled attempt-1 with a live attempt-2 must be SUPERSEDED, not requeued — requeuing it
        # would re-run the very attempt the newer attempt already replaced.
        if max_attempt.get(key, 0) > int(run.get("run_attempt") or 1):
            skipped.append({**run, "why": "superseded: a newer attempt of this run is on this branch"})
            continue
        if newest.get(key, created) > created:
            skipped.append({**run, "why": "superseded: a later run of this workflow is on this branch"})
            continue
        if _job_count(repo, run) == 0:
            # GitHub answers `gh run rerun --failed` on a cancelled run with no jobs with "This
            # workflow run cannot be retried" — nothing was instantiated, so a retry is a
            # DECISION GitHub has already made (issue #2295). Skip it now (the DRY classifier),
            # so the sweep and the runtime both record it as skipped, never failed.
            skipped.append({**run, "why": "no jobs instantiated: GitHub will not retry this run"})
            continue
        requeue.append(run)
    return requeue, skipped


#: A cancelled run that had already been in flight this long is a STALL, not a supersede (#846,
#: incident #767: a macOS row sat inside `make ci-unit` for 105 minutes and the PR owner cancelled to
#: escape it). The distinction matters because a stall is a fact about the JOB, and it is invisible to
#: an alarm that only sees `queued` rows - the run had a runner and was working.
STALL_MIN_MINUTES = 30


def _minutes(run: dict) -> float:
    """How long the run was in flight: `run_started_at` (or `created_at`) to `updated_at`."""
    def _at(value: str | None) -> "dt.datetime | None":
        if not value:
            return None
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))

    start = _at(run.get("run_started_at")) or _at(run.get("created_at"))
    end = _at(run.get("updated_at"))
    if not start or not end:
        return 0.0
    return max(0.0, (end - start).total_seconds() / 60.0)


def stalls(runs: list[dict], minimum_minutes: float = STALL_MIN_MINUTES) -> list[dict]:
    """The cancelled runs that had been RUNNING a long time - candidates for a hung job, not a supersede.

    `gh pr checks` renders these as `fail` and a queue alarm cannot see them at all, so a single job that
    hangs is read either as broken code or as nothing. Reporting the shape separately is what turns
    incident #767 into a comment instead of a cancel.
    """
    out: list[dict] = []
    for run in runs:
        if run.get("conclusion") != "cancelled":
            continue
        minutes = _minutes(run)
        if minutes >= minimum_minutes:
            out.append({**run, "minutes": round(minutes, 1)})
    return sorted(out, key=lambda r: r["minutes"], reverse=True)


def rerun(repo: str, run: dict, dry: bool) -> str:
    """Re-run one cancelled run's jobs; returns its recorded status.

    Returns:
      "reran"  a new attempt was dispatched (or would be, under `--dry`)
      "skip"   GitHub REFUSED the retry ("This workflow run cannot be retried") — a
               decision, recorded as skipped so the sweep's exit stays 0 (#2295)
      "dry"    a dry/plan run: nothing dispatched, the plan just names it

    A refusal is GitHub answering *decidedly*, never a transient failure: retrying the sweep
    cannot clear it, so it is recorded (not aborted) and the healer moves on. Every other
    non-zero return (rate limit, 5xx, auth) still raises, so a real problem is not swallowed.
    """
    if dry:
        print(f"[requeue] DRY would re-run {run['id']} {run.get('name')} "
              f"{(run.get('head_branch') or '')}@{str(run.get('head_sha'))[:7]}")
        return "dry"
    rc, err = _gh_no_raise("run", "rerun", str(run["id"]), "--repo", repo, "--failed")
    if rc == 0:
        print(f"[requeue] re-ran {run['id']} {run.get('name')} "
              f"{(run.get('head_branch') or '')}@{str(run.get('head_sha'))[:7]}")
        return "reran"
    if any(marker in err for marker in NON_RETRYABLE_MARKERS):
        run["why"] = f"GitHub will not retry this run ({err})"
        return "skip"
    raise SystemExit(f"[requeue] gh run rerun {run['id']} --repo {repo} --failed failed "
                     f"({rc}): {err}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Re-run the CI runs a bulk cancel killed (issue #843)")
    ap.add_argument("cmd", choices=("plan", "run"))
    ap.add_argument("--repo", default="asimov-agent/llgenie")
    ap.add_argument("--window", default=DEFAULT_WINDOW, help=f"how far back to heal (default {DEFAULT_WINDOW})")
    ap.add_argument("--dry", action="store_true", help="re-run nothing, print the plan")
    a = ap.parse_args(argv)

    window = parse_window(a.window)
    requeue, skipped = plan(a.repo, window)
    dry = a.dry or a.cmd == "plan"
    for run in requeue:
        status = rerun(a.repo, run, dry=dry)
        if status == "skip":          # a decision, not a failure: route it to the skip bucket
            skipped.append(run)
    for run in skipped:
        print(f"[requeue] keep {run['id']} {(run.get('head_branch') or '')}@{str(run.get('head_sha'))[:7]} "
              f"- {run['why']}")
    verb = "would re-run" if dry else "re-ran"
    print(f"[requeue] {verb} {len(requeue)} cancelled run(s) in the last {a.window}; "
          f"kept {len(skipped)} run(s) alone (superseded or refused)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
