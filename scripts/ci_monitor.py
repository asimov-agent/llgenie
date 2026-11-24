#!/usr/bin/env python3
"""The host CI monitor snapshot and triage (issues #3013, #3019).

`make ci-monitor` asks one question, every monitor tick: *what on this repo needs an agent right
now?* It reads the pipelines through the `gh` CLI — read-only, never a rerun/dispatch (queue-pumping
is forbidden by AGENTS) — and prints the incident snapshot:

- `MAIN-RED run=<id> workflow=<name> conclusion=<c>` — a completed main-branch run that failed,
  was cancelled, or timed out AND is still its workflow's newest completed run on `main` (a red a
  newer completed main run of the same workflow turned green is history, not an incident — issue
  #3048: 20 of the 29 reds in the measured 72 h window were exactly that);
- `PR-CHECKS pr=<n> head=<sha9> failed=<k>` — an open non-draft PR with `k` failing check buckets;
- `PR-MERGE pr=<n> head=<sha9> merge=<DIRTY|BEHIND>` — an open PR that cannot auto-merge as-is;
- `PR-REVIEW pr=<n> head=<sha9> decision=CHANGES_REQUESTED` — a reviewer holding the PR;
- `MONITOR-OK` — nothing needs attention;
- `MONITOR-ERROR gh-fetch-failed` — the reads themselves failed (detail on stderr).

The snapshot is byte-stable while the incident set is unchanged: lines are sorted and carry no
timestamps, in-flight/pending states are deliberately NOT incidents (they are expected transitions).
The Hermes monitor cron feeds exactly this stdout to its hash-gate: unchanged output suppresses the
agent, a changed snapshot wakes it with the diff.

`make ci-monitor-triage` (`--triage`, issue #3019) prints the SAME snapshot first, then routes each
incident to the run-failure reactor in file-only mode: every `MAIN-RED` run id, and for every
`PR-CHECKS` incident the REPRESENTATIVE completed failed runs that `pr_head_routing_plan` picks on
that PR's full head sha (issue #3047: a PR-CHECKS incident is a (PR, failing check bucket) pair, not
a run — newest red first, at most three reads per workflow, one run per failing step class), is
handed to `run_failure_reactor.route(..., file_only=True)` — the reactor files its marker-deduped
issue and dispatches NOTHING (fix-bot dispatch stays a CI/human action). A head that is still
queued/in_progress is named to the queued-alarm lane (`TRIAGE-QUEUED pr=<n> ... owner=queued-alarm`)
and routes nothing, and each PR prints one `PR-ROUTE pr=<n> routed=<r> suppressed=<s> aged=<a>`
summary. Each routing prints one verdict line (`TRIAGE-MAIN run=<id> routed rc=<rc>` /
`TRIAGE-PR pr=<n> run=<id> workflow=<wf> classes=<c> routed rc=<rc>`); `--dry` previews without
filing. `MONITOR-OK`/`MONITOR-ERROR` route nothing.

`--include-superseded` (`make ci-monitor INCLUDE_SUPERSEDED=1`) additionally prints
`MAIN-SUPERSEDED run=<id> workflow=<name> conclusion=<c> superseded_by=<id>` lines for the reds the
newest completed main run of each workflow replaced — a human read of recent history. Those lines are
never incidents and `--triage` never routes them, so the cron hash-gate stays incident-only by
default (issue #3048).

All `gh` traffic goes through an injectable `fetch` seam so the unit battery replays recorded
payloads with zero network (the probe-replay precedent).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

import run_failure_reactor
from proc import run_checked

# Conclusions that are incidents once a run is COMPLETED. In-flight states (queued/in_progress/
# waiting) and neutral outcomes (success, skipped) are deliberately absent: their transitions are
# noise a monitor must not wake an agent for.
MAIN_RED_CONCLUSIONS = ("failure", "cancelled", "timed_out")
# A completed red run is an incident only while it is RECENT. Batched cancels and old failures
# age out of the window so the monitor reports the board as it is, not as it was last week.
MONITOR_MAX_AGE_HOURS = 72
# Merge states that block the auto-merge landing and are actionable (rebase onto latest main).
PR_MERGE_INCIDENTS = ("DIRTY", "BEHIND")
# Review decisions a reviewer left for the agent to answer (AGENTS: PR review comments mandatory).
PR_REVIEW_INCIDENTS = ("CHANGES_REQUESTED",)
MONITOR_OK = "MONITOR-OK"
MONITOR_ERROR = "MONITOR-ERROR gh-fetch-failed"


class Fetch:
    """Default seam: read-only gh calls through the scripts/proc.py policy seam."""

    def __init__(self, repo: str, main_limit: int = 100) -> None:
        self.repo = repo
        self.main_limit = main_limit

    def main_runs(self) -> list[dict[str, Any]]:
        out = run_checked(
            [
                "gh", "run", "list", "--repo", self.repo, "--branch", "main",
                "--limit", str(self.main_limit),
                "--json", "databaseId,workflowName,headBranch,event,status,conclusion,updatedAt",
            ],
            timeout=120,
        )
        return json.loads(out)

    def open_prs(self) -> list[dict[str, Any]]:
        out = run_checked(
            [
                "gh", "pr", "list", "--repo", self.repo, "--state", "open", "--limit", "100",
                "--json", "number,headRefOid,headRefName,mergeStateStatus,reviewDecision,isDraft",
            ],
            timeout=120,
        )
        return json.loads(out)

    def pr_checks(self, pr_number: int) -> list[dict[str, Any]]:
        out = run_checked(
            ["gh", "pr", "checks", str(pr_number), "--repo", self.repo, "--json", "name,bucket"],
            timeout=120,
        )
        return json.loads(out)

    def runs_on_head(self, head_sha: str) -> list[dict[str, Any]]:
        """Every run recorded at this exact head commit, with its `status` (issues #3019, #3047).

        The read is `-c <sha>` (head-commit filter; `gh run list` has no `--pull` flag) and it is
        the ONE head read the triage leg makes. `status` stays in the payload because the routing
        plan must see a run that is still queued/in-progress and hand that PR to the queued-alarm
        lane instead of routing it; which rows are incidents is decided by
        `pr_head_routing_plan`, not by a second, filtered read of the same head (AGENTS.md: no
        second command path).
        """
        out = run_checked(
            [
                "gh", "run", "list", "--repo", self.repo, "-c", head_sha, "--limit", "50",
                "--json", "databaseId,workflowName,status,conclusion,updatedAt",
            ],
            timeout=120,
        )
        return [r for r in json.loads(out) if r.get("databaseId") is not None]

    def failing_jobs_for_run(self, run_id: Any) -> list[str]:
        """The failing job names of one run (issue #3047), read through the same gh seam.

        A run's failing job names ARE the failing step classes it stands for, so the routing plan
        can tell whether an older failed run adds a class a newer routed run already covers. A
        cancelled run with no failed job yields an empty list, and its workflow name alone is then
        the key it can be matched by.
        """
        out = run_checked(
            [
                "gh", "run", "view", str(run_id), "--repo", self.repo,
                "--json", "jobs",
            ],
            timeout=120,
        )
        jobs = json.loads(out).get("jobs") or []
        return [str(j.get("name") or "") for j in jobs
                if str(j.get("conclusion")) in MAIN_RED_CONCLUSIONS]


def _aged_out(run: Mapping[str, Any], now: datetime | None, max_age_hours: int | None) -> bool:
    """True when the run's `updatedAt` stamp is older than the age window. A payload without an
    `updatedAt` (recorded probe data) is never age-filtered, so replayed snapshots stay byte-stable."""
    updated = str(run.get("updatedAt") or "")
    if now is None or max_age_hours is None or not updated:
        return False
    try:
        stamp = datetime.fromisoformat(updated.replace("Z", "+00:00"))
    except ValueError:
        return False
    return (now - stamp).total_seconds() > max_age_hours * 3600


def _run_order(run: Mapping[str, Any]) -> tuple[str, int]:
    """Chronological order of recorded runs: the `updatedAt` stamp first, the monotonic run id as
    tiebreak (recorded payloads may carry no stamp at all)."""
    return (str(run.get("updatedAt") or ""), int(run.get("databaseId") or 0))


def classify_main_runs(
    main_runs: Sequence[dict[str, Any]],
    now: datetime | None = None,
    max_age_hours: int | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split completed `main` runs into (live incidents, superseded) per workflow (issue #3048).

    A main workflow is incident-red only when its NEWEST completed run on `main` concluded
    `failure`/`cancelled`/`timed_out` and sits inside the age window. An older completed red of the
    same workflow was superseded by that newer run and is no longer an incident — this is what made
    20 of the 29 reds in the measured 72 h window fake incidents. A newer run that has not completed
    yet supersedes nothing: the workflow's outcome is still unknown, so the newest COMPLETED run
    decides. Superseded runs carry `supersededBy` (the run id that replaced them).
    """
    by_workflow: dict[str, list[dict[str, Any]]] = {}
    for run in main_runs:
        if str(run.get("headBranch")) == "main" and str(run.get("status")) == "completed":
            by_workflow.setdefault(str(run.get("workflowName")), []).append(dict(run))

    incidents: list[dict[str, Any]] = []
    superseded: list[dict[str, Any]] = []
    for runs in by_workflow.values():
        runs.sort(key=_run_order)
        newest, older = runs[-1], runs[:-1]
        if str(newest.get("conclusion")) in MAIN_RED_CONCLUSIONS and not _aged_out(
            newest, now, max_age_hours
        ):
            incidents.append(newest)
        for run in older:
            if str(run.get("conclusion")) in MAIN_RED_CONCLUSIONS:
                superseded.append({**run, "supersededBy": newest.get("databaseId")})
    return incidents, superseded


def main_red_runs(
    main_runs: Sequence[dict[str, Any]],
    now: datetime | None = None,
    max_age_hours: int | None = None,
) -> list[dict[str, Any]]:
    """The MAIN-RED incident set: the live reds from `classify_main_runs` — a completed main-branch
    red that is its workflow's newest completed run on `main`. One incident definition for both the
    snapshot and the triage, so the two can never disagree (issues #3019, #3048).
    """
    incidents, _superseded = classify_main_runs(main_runs, now=now, max_age_hours=max_age_hours)
    return incidents


def pr_check_failures(
    open_prs: Sequence[dict[str, Any]],
    checks_by_pr: Mapping[int, Sequence[Mapping[str, Any]]],
) -> list[tuple[int, str, int]]:
    """PR-CHECKS incidents as (number, FULL head sha, failing bucket count) — draft PRs ignored."""
    out: list[tuple[int, str, int]] = []
    for pr in open_prs:
        if pr.get("isDraft"):
            continue
        number = int(pr["number"])
        head = str(pr.get("headRefOid") or "")
        failed = sum(1 for c in checks_by_pr.get(number, []) if str(c.get("bucket")) == "fail")
        if failed:
            out.append((number, head, failed))
    return out


def snapshot_lines(
    main_runs: Sequence[dict[str, Any]],
    open_prs: Sequence[dict[str, Any]],
    checks_by_pr: Mapping[int, Sequence[Mapping[str, Any]]],
    now: datetime | None = None,
    max_age_hours: int | None = None,
    include_superseded: bool = False,
) -> list[str]:
    """Pure snapshot: recorded payloads in, deterministic incident lines out.

    `include_superseded` adds the `MAIN-SUPERSEDED …` history lines (issue #3048); they are not
    incidents and the triage never routes them.
    """
    lines: list[str] = []
    incidents, superseded = classify_main_runs(main_runs, now=now, max_age_hours=max_age_hours)
    for run in incidents:
        lines.append(
            f"MAIN-RED run={run.get('databaseId')} "
            f"workflow={run.get('workflowName')} conclusion={run.get('conclusion')}"
        )
    if include_superseded:
        for run in superseded:
            lines.append(
                f"MAIN-SUPERSEDED run={run.get('databaseId')} "
                f"workflow={run.get('workflowName')} conclusion={run.get('conclusion')} "
                f"superseded_by={run.get('supersededBy')}"
            )
    for number, head, failed in pr_check_failures(open_prs, checks_by_pr):
        lines.append(f"PR-CHECKS pr={number} head={head[:9]} failed={failed}")
    for pr in open_prs:
        if pr.get("isDraft"):
            continue
        head = str(pr.get("headRefOid") or "")[:9]
        merge_state = str(pr.get("mergeStateStatus") or "")
        if merge_state in PR_MERGE_INCIDENTS:
            lines.append(f"PR-MERGE pr={pr['number']} head={head} merge={merge_state}")
        if str(pr.get("reviewDecision") or "") in PR_REVIEW_INCIDENTS:
            lines.append(f"PR-REVIEW pr={pr['number']} head={head} decision=CHANGES_REQUESTED")
    return sorted(lines)


PENDING_STATUSES = ("queued", "in_progress", "waiting")
# How deep the plan may look inside one workflow: the candidate pool is bounded per workflow, so the
# routing cost cannot grow with how much CI history a head happens to carry (issue #3047 measured 27
# reactor routings for 7 PRs because every historical red run of every workflow on a head got routed).
MAX_RUNS_PER_WORKFLOW = 3


def _check_key(name: Any) -> str:
    """The comparable part of a check or job name (issue #3047).

    Lower-cased, whitespace-collapsed, the workflow's ` \u2014 <description>` suffix dropped, and a
    `lane / job` pair reduced to its job part: the `gh pr checks` bucket `linux / unit` and that run's
    failing job name `linux / unit` become the same key, while two different engine matrix jobs stay
    different keys.
    """
    text = re.sub(r"\s+", " ", str(name or "").strip().lower())
    text = text.split(" \u2014 ")[0].strip()
    parts = [part.strip() for part in text.split("/")]
    return parts[-1] if len(parts) > 1 else text


def pr_head_routing_plan(
    runs: Sequence[Mapping[str, Any]],
    failing_buckets: Sequence[str],
    classes_of: Any,
    now: datetime | None = None,
    max_age_hours: int | None = None,
    max_runs_per_workflow: int = MAX_RUNS_PER_WORKFLOW,
) -> dict[str, Any]:
    """Which runs on ONE PR head the reactor should be handed (issue #3047).

    A PR-CHECKS incident is a (PR, failing check bucket) pair, not a run. The head commit carries
    every historical failed run of every workflow it triggered, and routing all of them spent 27
    reactor calls in one tick for the seven engine-bump PRs — most of them runs that explained none
    of the PR's failing buckets. So the plan covers the buckets instead of the history: newest red
    first (at most `max_runs_per_workflow` deep per workflow), and a run is routed only while it
    stands for a failing bucket no routed run stands for yet. A red run that explains no failing
    bucket is `suppressed`, never routed.

    A head that is still running belongs to the queued-alarm lane (issue #3047): a `queued`,
    `in_progress` or `waiting` run on the head means the outcome is not known yet, so nothing is
    routed for that PR and the plan names the lane that owns it.

    Returns `{"plan": [{"run", "workflow", "classes"}], "queued": [run ids], "aged": n,
    "suppressed": n, "uncovered": [bucket names]}`, where `classes` are the failing buckets the
    routed run stands for, `suppressed` counts every fresh completed red run on the head the plan
    declined to route, and `uncovered` are the buckets no completed failed run on the head explains.
    """
    wanted = sorted({str(b) for b in failing_buckets if str(b)})
    queued = sorted(
        (r for r in runs if str(r.get("status")) in PENDING_STATUSES),
        key=lambda r: -int(r.get("databaseId") or 0),
    )
    if queued:
        return {"plan": [], "queued": [int(r.get("databaseId") or 0) for r in queued],
                "aged": 0, "suppressed": 0, "uncovered": wanted}

    reds: dict[str, list[dict[str, Any]]] = {}
    aged = 0
    for run in runs:
        if str(run.get("status")) != "completed":
            continue
        if str(run.get("conclusion")) not in MAIN_RED_CONCLUSIONS:
            continue
        if _aged_out(run, now, max_age_hours):
            aged += 1
            continue
        reds.setdefault(str(run.get("workflowName")), []).append(dict(run))

    # Newest red first, then round-robin across workflows: one workflow's deep history cannot be the
    # only candidate pool, and no workflow is examined deeper than `max_runs_per_workflow`.
    for rows in reds.values():
        rows.sort(key=_run_order, reverse=True)
    candidates: list[dict[str, Any]] = []
    for rank in range(max_runs_per_workflow):
        for workflow in sorted(reds):
            if len(reds[workflow]) > rank:
                candidates.append(reds[workflow][rank])

    wanted_keys = {_check_key(b): b for b in wanted}
    red_total = sum(len(rows) for rows in reds.values())
    covered: dict[str, int] = {}
    picked: dict[int, dict[str, Any]] = {}
    order: list[int] = []
    for row in candidates:
        if len(covered) >= len(wanted_keys):
            break  # every failing bucket already has a representative
        workflow = str(row.get("workflowName"))
        run_id = int(row.get("databaseId") or 0)
        classes = [str(c) for c in classes_of(run_id) if str(c)]
        keys = {_check_key(c) for c in classes} | {_check_key(workflow)}
        fresh = [b for k, b in sorted(wanted_keys.items()) if k in keys and b not in covered]
        if not fresh:
            continue  # a red run that stands for no failing bucket
        for bucket in fresh:
            covered[bucket] = run_id
        if run_id not in picked:
            picked[run_id] = {"run": run_id, "workflow": workflow, "classes": []}
            order.append(run_id)
        picked[run_id]["classes"] = sorted(b for b, r in covered.items() if r == run_id)

    return {
        "plan": [picked[run_id] for run_id in order],
        "queued": [],
        "aged": aged,
        "suppressed": red_total - len(order),
        "uncovered": sorted(b for b in wanted if b not in covered),
    }


def triage_incidents(
    fetch: Any,
    repo: str,
    main_runs: Sequence[dict[str, Any]],
    open_prs: Sequence[dict[str, Any]],
    checks_by_pr: Mapping[int, Sequence[Mapping[str, Any]]],
    dry: bool = False,
    now: datetime | None = None,
    max_age_hours: int | None = None,
) -> list[str]:
    """Route every snapshot incident through the reactor in file-only mode; verdict lines out.

    MAIN-RED routes the incident run itself; a PR-CHECKS incident routes the REPRESENTATIVE runs
    `pr_head_routing_plan` picks on the PR's full head sha (issue #3047), and a head that is still
    queued is handed to the queued-alarm lane with no routing at all. The reactor's own
    `[run-fixer]` verdicts print as it works; each routing adds one `TRIAGE-*` line here, and each
    PR adds one `PR-ROUTE` summary that names what the dedupe suppressed. Nothing here dispatches
    or reruns (issue #3019).
    """
    verdicts: list[str] = []
    for run in main_red_runs(main_runs, now=now, max_age_hours=max_age_hours):
        run_id = int(run.get("databaseId") or 0)
        rc = run_failure_reactor.route(repo, run_id, dry=dry, file_only=True)
        verdicts.append(f"TRIAGE-MAIN run={run_id} routed rc={rc}")
    # AGENTS.md: a failed PR pipeline is fixed ON ITS BRANCH, so every routing names that branch.
    owners = {int(pr["number"]): str(pr.get("headRefName") or "") for pr in open_prs}
    for number, head, _failed in pr_check_failures(open_prs, checks_by_pr):
        if not head:
            verdicts.append(f"TRIAGE-PR pr={number} no-head-sha routed rc=1")
            continue
        buckets = [str(c.get("name") or "") for c in checks_by_pr.get(number, [])
                   if str(c.get("bucket")) == "fail"]
        plan = pr_head_routing_plan(
            fetch.runs_on_head(head), buckets, fetch.failing_jobs_for_run,
            now=now, max_age_hours=max_age_hours,
        )
        if plan["queued"]:
            verdicts.append(
                f"TRIAGE-QUEUED pr={number} head={head[:9]} owner=queued-alarm "
                f"runs={','.join(str(r) for r in plan['queued'])}"
            )
            continue
        if not plan["plan"]:
            verdicts.append(
                f"TRIAGE-PR pr={number} head={head[:9]} no-completed-failed-run found"
                + (f" aged={plan['aged']}" if plan["aged"] else "")
            )
            continue
        for item in plan["plan"]:
            rc = run_failure_reactor.route(repo, item["run"], dry=dry, file_only=True)
            verdicts.append(
                f"TRIAGE-PR pr={number} run={item['run']} workflow={item['workflow']} "
                f"owner={owners.get(number, '')} classes={','.join(item['classes'])} "
                f"routed rc={rc}"
            )
        uncovered = f" uncovered={','.join(plan['uncovered'])}" if plan["uncovered"] else ""
        verdicts.append(
            f"PR-ROUTE pr={number} head={head[:9]} routed={len(plan['plan'])} "
            f"suppressed={plan['suppressed']} aged={plan['aged']}{uncovered}"
        )
    return verdicts


def fetch_incidents(fetch: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]],
                                         dict[int, list[dict[str, Any]]]]:
    """The three gh reads the snapshot and the triage share (one read path for both modes)."""
    main_runs = fetch.main_runs()
    open_prs = [pr for pr in fetch.open_prs() if not pr.get("isDraft")]
    checks_by_pr = {int(pr["number"]): fetch.pr_checks(int(pr["number"])) for pr in open_prs}
    return main_runs, open_prs, checks_by_pr


def build_snapshot(
    fetch: Any, max_age_hours: int = MONITOR_MAX_AGE_HOURS, include_superseded: bool = False
) -> str:
    try:
        main_runs, open_prs, checks_by_pr = fetch_incidents(fetch)
    except Exception as exc:  # the snapshot stays byte-stable even when the reads fail
        print(f"{MONITOR_ERROR}: {exc}", file=sys.stderr)
        return MONITOR_ERROR
    lines = snapshot_lines(
        main_runs, open_prs, checks_by_pr,
        now=datetime.now(timezone.utc), max_age_hours=max_age_hours,
        include_superseded=include_superseded,
    )
    return "\n".join(lines) if lines else MONITOR_OK


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print the gh-backed CI incident snapshot; --triage also routes incidents "
                    "(issues #3013/#3019)."
    )
    parser.add_argument("--repo", default="asimov-agent/llgenie")
    parser.add_argument("--main-limit", type=int, default=100)
    parser.add_argument(
        "--max-age-hours", type=int, default=MONITOR_MAX_AGE_HOURS,
        help="A completed red main run counts as an incident only while updated within this window.",
    )
    parser.add_argument("--fetch", default=None, help="importable callable() -> Fetch (test seam)")
    parser.add_argument(
        "--triage", action="store_true",
        help="after the snapshot, route each MAIN-RED/PR-CHECKS incident to the run-failure "
             "reactor in file-only mode (files deduped issues, dispatches nothing)",
    )
    parser.add_argument("--dry", action="store_true",
                        help="with --triage: print the routing plan, file nothing")
    parser.add_argument("--include-superseded", action="store_true",
                        help="also print MAIN-SUPERSEDED history lines (never incidents, never "
                             "routed; issue #3048)")
    args = parser.parse_args(argv)
    if args.fetch:
        import importlib

        module_name, _, func_name = args.fetch.partition(":")
        fetch = getattr(importlib.import_module(module_name), func_name)()
    else:
        fetch = Fetch(repo=args.repo, main_limit=args.main_limit)
    repo = str(getattr(fetch, "repo", args.repo))
    if not args.triage:
        print(build_snapshot(fetch, max_age_hours=args.max_age_hours,
                             include_superseded=args.include_superseded))
        return 0
    try:
        main_runs, open_prs, checks_by_pr = fetch_incidents(fetch)
    except Exception as exc:
        print(f"{MONITOR_ERROR}: {exc}", file=sys.stderr)
        return 0
    now = datetime.now(timezone.utc)
    lines = snapshot_lines(
        main_runs, open_prs, checks_by_pr, now=now, max_age_hours=args.max_age_hours,
        include_superseded=args.include_superseded,
    )
    print("\n".join(lines) if lines else MONITOR_OK)
    if lines:
        for verdict in triage_incidents(
            fetch, repo, main_runs, open_prs, checks_by_pr,
            dry=args.dry, now=now, max_age_hours=args.max_age_hours,
        ):
            print(verdict)
    return 0


if __name__ == "__main__":
    sys.exit(main())
